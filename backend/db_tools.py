import os
import oracledb
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    """
    Establish and return a connection to the Oracle Database.
    Relies on environment variables for credentials and mTLS configuration.
    """
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    dsn = os.getenv("DB_DSN")
    tns_admin = os.getenv("TNS_ADMIN")
    wallet_password = os.getenv("DB_WALLET_PASSWORD")

    if not all([user, password, dsn]):
        raise ValueError("Missing required database credentials in environment variables.")

    # In python-oracledb, Thin Mode is the default and does not require Oracle Instant Client.
    # It supports mTLS (wallets) natively. We can pass the config_dir and wallet_location here.
    conn_kwargs = {
        "user": user,
        "password": password,
        "dsn": dsn
    }
    
    if tns_admin:
        conn_kwargs["config_dir"] = tns_admin
        conn_kwargs["wallet_location"] = tns_admin
        if wallet_password:
            conn_kwargs["wallet_password"] = wallet_password

    return oracledb.connect(**conn_kwargs)

def get_pillars_and_modules(connection):
    """
    Retrieve distinct Pillars and Modules from fusion_table_comments
    to help narrow down search context when needed.
    """
    query = """
        SELECT DISTINCT pillar, module 
        FROM fusion_table_comments
        WHERE pillar IS NOT NULL AND module IS NOT NULL
        ORDER BY pillar, module
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()

    return [{"pillar": row[0], "module": row[1]} for row in results]

def discover_tables(connection, search_query: str, pillar: str = None, module: str = None, limit: int = 5):
    """
    Perform a semantic vector search to find tables matching the user's query.
    Filters by exact pillar and module if provided.
    """
    # Base query combining fusion_table_comments and fusion_tab_vectors
    # Using VECTOR_DISTANCE for similarity between the query string vector and SHORT_VECTOR
    # VECTOR_EMBEDDING generates the vector for the search string using the in-database model
    
    query = """
        SELECT 
            c.TABLE_NAME, 
            c.SHORT_COMMENTS, 
            c.PILLAR, 
            c.MODULE,
            VECTOR_DISTANCE(
                v.SHORT_VECTOR, 
                VECTOR_EMBEDDING(ALL_MINILM_L12_V2 USING :search_query AS DATA),
                COSINE
            ) as similarity_score
        FROM fusion_table_comments c
        JOIN fusion_tab_vectors v ON c.TABLE_NAME = v.TABLE_NAME
        WHERE v.VECTOR_TYPE = 3 -- Mapped to ALL_MINILM_L12_V2 (384-dim)
    """
    
    params = {"search_query": search_query}
    
    if pillar:
        query += " AND c.PILLAR = :pillar"
        params["pillar"] = pillar
        
    if module:
        query += " AND c.MODULE = :module"
        params["module"] = module
        
    # Order by closest semantic distance
    query += f" ORDER BY similarity_score ASC FETCH FIRST {limit} ROWS ONLY"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        results = cursor.fetchall()

    tables = []
    for row in results:
        tables.append({
            "table_name": row[0],
            "description": row[1],
            "pillar": row[2],
            "module": row[3],
            "distance_score": round(row[4], 4) if row[4] is not None else None
        })
        
    return tables

def get_table_metadata(connection, table_name: str):
    """
    Fetch structure, data types, and comments for a specific table 
    using Oracle's built-in data dictionary views.
    Returns the formatted text structure requested:
        ===TABLE NAME|DESCRIPTION
        ===COLUMN NAME|DATA TYPE|DESCRIPTION
    """
    query = """
        SELECT to_clob('===TABLE NAME|DESCRIPTION') dt, 1 ord from dual
        union all
        SELECT to_clob(at1.table_name||'|'|| at1.comments) dt , 2 ord
        FROM all_tab_comments at1
        WHERE at1.table_name= UPPER(:table_name)
        
        union all
        select to_clob('===COLUMN NAME|DATA TYPE|DESCRIPTION') dt, 3 ord from dual
        
        union all
        SELECT * FROM (
            SELECT to_clob(ac1.column_name||'|'||atc.data_type||'|'|| ac1.comments) dt, 4 ord
            FROM all_col_comments ac1
            JOIN all_tab_cols atc ON atc.table_name = ac1.table_name AND atc.column_name = ac1.column_name
            WHERE ac1.table_name = UPPER(:table_name)
            ORDER BY atc.column_id asc
        )
        ORDER BY ORD ASC
    """

    with connection.cursor() as cursor:
        cursor.execute(query, {"table_name": table_name})
        results = cursor.fetchall()
        
    # Combine the CLOB texts into a single string
    formatted_schema = ""
    for row in results:
        clob_content = row[0].read() if hasattr(row[0], 'read') else str(row[0])
        formatted_schema += clob_content + "\n"
        
    return formatted_schema.strip()

def log_execution_history(connection, username: str, query: str, host: str):
    """
    Log or update the execution history of a query.
    If the exact query exists for this user/host, update the date.
    Otherwise, insert a new record.
    """
    with connection.cursor() as cursor:
        # Check if identical query already exists
        check_sql = "SELECT EXECUTION_ID FROM P4S_FUSION_EXECUTION_HISTORY WHERE USERNAME = :1 AND HOST = :2 AND DBMS_LOB.COMPARE(QUERY, TO_CLOB(:3)) = 0"
        cursor.execute(check_sql, [username, host, query])
        row = cursor.fetchone()

        if row:
            # Update existing
            update_sql = "UPDATE P4S_FUSION_EXECUTION_HISTORY SET EXECUTION_DATE = SYSDATE WHERE EXECUTION_ID = :1"
            cursor.execute(update_sql, [row[0]])
        else:
            # Insert new
            # Assuming EXECUTION_ID is either GENERATED ALWAYS AS IDENTITY or we must handle it. 
            # Often it's generated, but let's safely insert without it if possible, or fallback.
            # Usually, standard practice for these tables if they lack sequence is to use NVL MAX.
            id_sql = "SELECT NVL(MAX(EXECUTION_ID), 0) + 1 FROM P4S_FUSION_EXECUTION_HISTORY"
            cursor.execute(id_sql)
            next_id = cursor.fetchone()[0]

            insert_sql = """
            INSERT INTO P4S_FUSION_EXECUTION_HISTORY 
            (EXECUTION_ID, USERNAME, EXECUTION_DATE, QUERY, HOST) 
            VALUES (:1, :2, SYSDATE, :3, :4)
            """
            cursor.execute(insert_sql, [next_id, username, query, host])

        connection.commit()
