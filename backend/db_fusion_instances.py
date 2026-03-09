import oracledb
from typing import List, Dict, Optional

def get_instances(conn: oracledb.Connection) -> List[Dict]:
    cursor = conn.cursor()
    query = """
    SELECT ENV_ID, ENV_NAME, FUSION_USER_NAME, HOST, DEFAULT_INSTANCE
    FROM P4S_USER_ENVIRONMENTS
    ORDER BY ENV_ID
    """
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return results

def get_instance_by_id(conn: oracledb.Connection, env_id: int) -> Optional[Dict]:
    cursor = conn.cursor()
    query = """
    SELECT ENV_ID, ENV_NAME, FUSION_USER_NAME, HOST, DEFAULT_INSTANCE
    FROM P4S_USER_ENVIRONMENTS
    WHERE ENV_ID = :1
    """
    cursor.execute(query, [env_id])
    row = cursor.fetchone()
    if not row:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))

def _set_other_defaults_to_no(cursor, ignore_env_id=None):
    if ignore_env_id:
        cursor.execute("UPDATE P4S_USER_ENVIRONMENTS SET DEFAULT_INSTANCE = 'N' WHERE ENV_ID != :1", [ignore_env_id])
    else:
        cursor.execute("UPDATE P4S_USER_ENVIRONMENTS SET DEFAULT_INSTANCE = 'N'")

def create_instance(conn: oracledb.Connection, env_name: str, fusion_user_name: str, host: str, default_instance: str) -> int:
    cursor = conn.cursor()
    
    if default_instance == 'Y':
        _set_other_defaults_to_no(cursor)
    
    cursor.execute("SELECT NVL(MAX(ENV_ID), 0) + 1 FROM P4S_USER_ENVIRONMENTS")
    new_id = cursor.fetchone()[0]
    
    user_id = 1 # Mock user ID for now
    
    insert_query = """
    INSERT INTO P4S_USER_ENVIRONMENTS (ENV_ID, USER_ID, ENV_NAME, FUSION_USER_NAME, HOST, DEFAULT_INSTANCE)
    VALUES (:1, :2, :3, :4, :5, :6)
    """
    cursor.execute(insert_query, [new_id, user_id, env_name, fusion_user_name, host, default_instance])
    conn.commit()
    return new_id

def update_instance(conn: oracledb.Connection, env_id: int, env_name: str, fusion_user_name: str, host: str, default_instance: str):
    cursor = conn.cursor()
    
    if default_instance == 'Y':
        _set_other_defaults_to_no(cursor, ignore_env_id=env_id)
        
    update_query = """
    UPDATE P4S_USER_ENVIRONMENTS
    SET ENV_NAME = :1, FUSION_USER_NAME = :2, HOST = :3, DEFAULT_INSTANCE = :4
    WHERE ENV_ID = :5
    """
    cursor.execute(update_query, [env_name, fusion_user_name, host, default_instance, env_id])
    conn.commit()

def delete_instance(conn: oracledb.Connection, env_id: int):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM P4S_USER_ENVIRONMENTS WHERE ENV_ID = :1", [env_id])
    conn.commit()
