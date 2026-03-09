import os
import sys
import json
import requests
import traceback
import sqlglot
from sqlglot import exp

# Ensure we can import db_tools from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db_tools

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.1:latest"

def create_table_if_not_exists(conn):
    check_sql = "SELECT count(*) FROM user_tables WHERE table_name = 'FUSION_TABLE_JOINS'"
    create_sql = """
    CREATE TABLE FUSION_TABLE_JOINS (
        SOURCE_QUERY_ID NUMBER,
        SOURCE_TABLE VARCHAR2(128),
        SOURCE_COLUMN VARCHAR2(128),
        TARGET_TABLE VARCHAR2(128),
        TARGET_COLUMN VARCHAR2(128),
        CONSTRAINT unique_fusion_join UNIQUE (SOURCE_TABLE, SOURCE_COLUMN, TARGET_TABLE, TARGET_COLUMN)
    )
    """
    with conn.cursor() as cursor:
        cursor.execute(check_sql)
        if cursor.fetchone()[0] == 0:
            print("Creating FUSION_TABLE_JOINS table...")
            cursor.execute(create_sql)
            conn.commit()

def extract_joins_with_sqlglot(sql_content):
    joins = []
    try:
        # Parse the SQL using the Oracle dialect
        ast = sqlglot.parse_one(sql_content, read="oracle")
        
        # Build alias map: lookup[alias.upper()] = table_name.upper()
        # Also handle tables that lack aliases
        tables = list(ast.find_all(exp.Table))
        aliases = {}
        for t in tables:
            name = t.name.upper()
            alias = t.alias.upper() if t.alias else name
            aliases[alias] = name

        # Find all equalities inside WHERE/JOIN ON clauses
        for eq in ast.find_all(exp.EQ):
            if isinstance(eq.left, exp.Column) and isinstance(eq.right, exp.Column):
                left_table = eq.left.table.upper() if eq.left.table else ""
                right_table = eq.right.table.upper() if eq.right.table else ""
                
                # Check that both columns are explicitly qualified and reference different tables
                if left_table and right_table and left_table != right_table:
                    real_left = aliases.get(left_table, left_table)
                    real_right = aliases.get(right_table, right_table)
                    
                    joins.append({
                        "source_table": real_left,
                        "source_column": eq.left.name.upper(),
                        "target_table": real_right,
                        "target_column": eq.right.name.upper()
                    })
        return joins, None
    except Exception as e:
        return None, str(e)

def extract_joins_with_ollama(sql_content):
    prompt = f"""
    Analyze the following Oracle SQL query and extract all table join relationships.
    Ignore literal filters (e.g. status = 'ACTIVE').
    Also replace table aliases with the actual base table names from the FROM/JOIN clauses.
    Return ONLY a valid JSON array of objects with these exact keys:
    [
      {{"source_table": "TABLE_A", "source_column": "COL_1", "target_table": "TABLE_B", "target_column": "COL_2"}}
    ]
    Format strictly as JSON. No markdown backticks, no explanation, no formatting blocks.

    Query:
    {sql_content}
    """
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=90)
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        
        # Clean markdown if present
        if text.startswith("```json"): text = text[7:]
        elif text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        parsed = json.loads(text.strip())
        if isinstance(parsed, list):
            # Normalize keys to uppercase to match Oracle conventions
            joins = []
            for j in parsed:
                joins.append({
                    "source_table": str(j.get("source_table", "")).upper(),
                    "source_column": str(j.get("source_column", "")).upper(),
                    "target_table": str(j.get("target_table", "")).upper(),
                    "target_column": str(j.get("target_column", "")).upper()
                })
            return joins, None
        return None, "Invalid JSON structure from LLM"
    except Exception as e:
        return None, str(e)

def insert_joins(conn, query_id, joins):
    inserted = 0
    with conn.cursor() as cursor:
        for j in joins:
            st = j.get("source_table")
            sc = j.get("source_column")
            tt = j.get("target_table")
            tc = j.get("target_column")
            
            if not st or not sc or not tt or not tc:
                continue

            # Ensure consistent ordering for unique constraint checking.
            # Alphabetically sort the table names so A=B and B=A are treated exactly identical.
            if st > tt:
                st, tt = tt, st
                sc, tc = tc, sc
                
            merge_sql = """
            MERGE INTO FUSION_TABLE_JOINS trg
            USING (SELECT :1 AS qid, :2 AS st, :3 AS sc, :4 AS tt, :5 AS tc FROM dual) src
            ON (trg.SOURCE_TABLE = src.st AND trg.SOURCE_COLUMN = src.sc 
                AND trg.TARGET_TABLE = src.tt AND trg.TARGET_COLUMN = src.tc)
            WHEN NOT MATCHED THEN
                INSERT (SOURCE_QUERY_ID, SOURCE_TABLE, SOURCE_COLUMN, TARGET_TABLE, TARGET_COLUMN)
                VALUES (src.qid, src.st, src.sc, src.tt, src.tc)
            """
            try:
                cursor.execute(merge_sql, [query_id, st, sc, tt, tc])
                inserted += cursor.rowcount
            except Exception as e:
                # Can be silently ignored, but logging helps transparency if unexpected DB constraints are hit
                print(f"Error inserting join {st}.{sc} = {tt}.{tc}: {e}")
        conn.commit()
    return inserted

def main():
    try:
        conn = db_tools.get_db_connection()
    except Exception as e:
        print(f"Database connection failed: {e}")
        return

    try:
        create_table_if_not_exists(conn)
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT ID, QUERY FROM P4S_FUSION_QUERIES WHERE QUERY IS NOT NULL")
            rows = cursor.fetchall()
            
        print(f"Found {len(rows)} queries to process.")
        
        total_joins_found = 0
        total_new_inserts = 0
        sqlglot_success = 0
        ollama_success = 0
        failures = 0
        
        for i, row in enumerate(rows):
            query_id = row[0]
            # Read CLOB text content
            sql_content = row[1].read() if hasattr(row[1], 'read') else str(row[1])
            
            print(f"Processing query {i+1}/{len(rows)} (ID: {query_id})...", end=" ")
            
            joins, err = extract_joins_with_sqlglot(sql_content)
            if joins is not None:
                inserted = insert_joins(conn, query_id, joins)
                sqlglot_success += 1
                total_joins_found += len(joins)
                total_new_inserts += inserted
                print(f"sqlglot extracted {len(joins)} relationships ({inserted} unique inserted).")
            else:
                # LLM fallback
                err_msg = (err or '')[:50].replace('\n', ' ')
                print(f"sqlglot parsing failed ({err_msg}...), trying Ollama...", end=" ")
                joins, err2 = extract_joins_with_ollama(sql_content)
                if joins is not None:
                    inserted = insert_joins(conn, query_id, joins)
                    ollama_success += 1
                    total_joins_found += len(joins)
                    total_new_inserts += inserted
                    print(f"Ollama extracted {len(joins)} relationships ({inserted} unique inserted).")
                else:
                    failures += 1
                    print(f"Ollama failed as well: {err2}")
                    
        print(f"\\n--- Extraction Complete ---")
        print(f"Total queries scanned: {len(rows)}")
        print(f"Parsed successfully by pure AST: {sqlglot_success}")
        print(f"Parsed successfully via Ollama fallback: {ollama_success}")
        print(f"Failed completely: {failures}")
        print(f"Total relationships extracted: {total_joins_found}")
        print(f"Total net-new insertions to database: {total_new_inserts}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
