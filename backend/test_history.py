import db_tools

try:
    conn = db_tools.get_db_connection()
    db_tools.log_execution_history(conn, "ASHWIN.SRINIVASAN@ORACLE.COM", "SELECT * FROM FND_LOOKUPS", "https://test.oraclecloud.com")
    print("Success")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
