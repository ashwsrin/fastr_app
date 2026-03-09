import requests
import xml.etree.ElementTree as ET
import base64
import csv
import io
import oracledb

def get_setup_payload(conn: oracledb.Connection, setup_name: str) -> str:
    cursor = conn.cursor()
    cursor.execute("SELECT SETUP_TEXT FROM p4s_fusion_setup_texts WHERE SETUP_TYPE = 'PAYLOAD' AND SETUP_NAME = :1", [setup_name])
    row = cursor.fetchone()
    if row:
        text = row[0]
        return text.read() if hasattr(text, 'read') else text
    raise Exception(f"Setup payload {setup_name} not found")

def execute_query(conn: oracledb.Connection, query: str, limit: int, host: str, username: str, password: str):
    wrapped_query = f"SELECT * FROM ({query}) WHERE rownum <= {limit}"
    encoded_query = wrapped_query.encode('utf-8').hex().upper()

    payload = get_setup_payload(conn, 'EXECUTE_RUN_REPORT')
    payload = payload.replace(':ATTRIBUTE_FORMAT', 'csv')
    payload = payload.replace(':ENCODED_VALUE', encoded_query)
    payload = payload.replace(':XDO_PATH', '/Custom/FusionGenerate/FusionGenerate.xdo')

    url = host.rstrip('/') + "/xmlpserver/services/ExternalReportWSSService"

    response = requests.post(url, data=payload, auth=(username, password), headers={'Content-Type': 'application/soap+xml; charset=utf-8'})

    if response.status_code == 401:
        return {"error": "Invalid username or password.", "needs_create": False}

    print(f"--- FUSION RAW RESPONSE ---\n{response.text}\n---------------------------")

    try:
        root = ET.fromstring(response.text)
    except Exception as e:
        print(f"Failed to parse XML: {e}")
        return {"error": f"{e}", "needs_create": False}
        
    ns = {'env': 'http://www.w3.org/2003/05/soap-envelope', 'pub': 'http://xmlns.oracle.com/oxp/service/PublicReportService'}

    if response.status_code == 500:
        reason_node = root.find('.//env:Reason/env:Text', ns)
        if reason_node is not None and reason_node.text:
            if 'generateReport failed: due to Invalid Report Absolute Path' in reason_node.text:
                return {"error": "Report not found on instance.", "needs_create": True}
            return {"error": reason_node.text.replace('/Custom/FusionGenerate/FusionGenerate.xdo', ''), "needs_create": False}
        return {"error": "Internal Server Error from Fusion", "needs_create": False}

    if response.status_code == 200:
        report_bytes_node = root.find('.//pub:reportBytes', ns)
        if report_bytes_node is None or not report_bytes_node.text:
            text_node = root.find('.//env:Text', ns)
            if text_node is not None and text_node.text and 'SQLSyntaxErrorException' in text_node.text:
                return {"error": "Invalid SQL Statement", "needs_create": False}
            return {"error": "Invalid SQL Statement or No Data Returned", "needs_create": False}

        csv_data = base64.b64decode(report_bytes_node.text).decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_data))
        rows = [row for row in reader]

        columns = []
        if len(rows) > 0:
            columns = list(rows[0].keys())
        
        # formatting to generic rows arrays for UI
        formatted_rows = []
        for row in rows:
            formatted_rows.append([row[col] for col in columns])

        return {"columns": columns, "rows": formatted_rows}

    return {"error": "Unknown error occurred.", "needs_create": False}

def create_report(conn: oracledb.Connection, host: str, username: str, password: str):
    url = host.rstrip('/') + "/xmlpserver/services/ExternalReportWSSService"
    
    dm_payload = get_setup_payload(conn, 'UPLOAD_REPORT_DM')
    rep_payload = get_setup_payload(conn, 'UPLOAD_REPORT_OBJ')

    headers = {'Content-Type': 'application/soap+xml; charset=utf-8'}
    
    resp1 = requests.post(url, data=dm_payload, auth=(username, password), headers=headers)
    if resp1.status_code != 200:
        return {"error": f"Error Occurred while creating Data Model. Status: {resp1.status_code}"}

    resp2 = requests.post(url, data=rep_payload, auth=(username, password), headers=headers)
    if resp2.status_code != 200:
        return {"error": f"Error Occurred while creating Report. Status: {resp2.status_code}"}

    return {"success": True}
