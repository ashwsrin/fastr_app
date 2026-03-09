from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import db_tools
import agent
import db_fusion_instances
import fusion_client

app = FastAPI(title="FASTR Backend Pilot")

# Enable CORS for the local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    prompt: str
    history: Optional[List[ChatMessage]] = []

class InstanceCreateRequest(BaseModel):
    env_name: str
    fusion_user_name: str
    host: str
    default_instance: str

class InstanceUpdateRequest(InstanceCreateRequest):
    env_id: int

class FusionExecuteRequest(BaseModel):
    query: str
    instance_id: int
    password: str
    limit: int = 50

class FusionCreateReportRequest(BaseModel):
    instance_id: int
    password: str

@app.get("/")
def read_root():
    return {"message": "Welcome to FASTR Backend"}

@app.get("/api/instances")
async def get_instances():
    conn = db_tools.get_db_connection()
    try:
        return db_fusion_instances.get_instances(conn)
    finally:
        conn.close()

@app.post("/api/instances")
async def create_instance(req: InstanceCreateRequest):
    conn = db_tools.get_db_connection()
    try:
        new_id = db_fusion_instances.create_instance(conn, req.env_name, req.fusion_user_name, req.host, req.default_instance)
        return {"id": new_id}
    finally:
        conn.close()

@app.put("/api/instances/{env_id}")
async def update_instance(env_id: int, req: InstanceUpdateRequest):
    conn = db_tools.get_db_connection()
    try:
        db_fusion_instances.update_instance(conn, env_id, req.env_name, req.fusion_user_name, req.host, req.default_instance)
        return {"success": True}
    finally:
        conn.close()

@app.delete("/api/instances/{env_id}")
async def delete_instance(env_id: int):
    conn = db_tools.get_db_connection()
    try:
        db_fusion_instances.delete_instance(conn, env_id)
        return {"success": True}
    finally:
        conn.close()

@app.get("/api/discover")
async def discover_tables(query: str, pillar: Optional[str] = None, module: Optional[str] = None, limit: int = 5):
    """
    Semantic search for tables based on the user's query.
    Takes advantage of Oracle 26ai/23ai vector search.
    """
    try:
        conn = db_tools.get_db_connection()
        try:
            results = db_tools.discover_tables(conn, search_query=query, pillar=pillar, module=module, limit=limit)
            return {"results": results}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metadata/{table_name}")
async def get_metadata(table_name: str):
    """
    Retrieves the table and column definitions directly from Oracle data dictionary views.
    """
    try:
        conn = db_tools.get_db_connection()
        try:
            schema_text = db_tools.get_table_metadata(conn, table_name)
            if not schema_text:
                raise HTTPException(status_code=404, detail=f"Table {table_name} not found.")
            return {"table_name": table_name, "metadata": schema_text}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    """
    Agentic generation logic. Takes user prompt and history, returns a state payload.
    The agent may discover tables or generate SQL autonomously.
    """
    try:
        # Pass conversation history to the agent execution
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history] if request.history else []
        response_data = agent.generate_response(request.prompt, history=history_dicts)
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute")
async def execute_query(request: FusionExecuteRequest):
    """
    Run the provided SQL against the specified Fusion instance.
    """
    conn = db_tools.get_db_connection()
    try:
        instance = db_fusion_instances.get_instance_by_id(conn, request.instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        
        result = fusion_client.execute_query(
            conn, 
            request.query, 
            request.limit, 
            instance['HOST'], 
            instance['FUSION_USER_NAME'], 
            request.password
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result)
            
        # Log successful execution to history
        try:
            db_tools.log_execution_history(conn, "ASHWIN.SRINIVASAN@ORACLE.COM", request.query, instance['HOST'])
        except Exception as log_err:
            print(f"Warning: Failed to log execution history: {log_err}")
            
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/execute/create-report")
async def create_report(request: FusionCreateReportRequest):
    """
    Create the BI Report on the instance if it does not exist.
    """
    conn = db_tools.get_db_connection()
    try:
        instance = db_fusion_instances.get_instance_by_id(conn, request.instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
            
        result = fusion_client.create_report(
            conn,
            instance['HOST'],
            instance['FUSION_USER_NAME'],
            request.password
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result['error'])
        return result
    finally:
        conn.close()

@app.get("/api/history")
async def get_execution_history(username: str = "ASHWIN.SRINIVASAN@ORACLE.COM"):
    """
    Fetch the execution history for the given user from P4S_FUSION_EXECUTION_HISTORY.
    """
    conn = db_tools.get_db_connection()
    try:
        cursor = conn.cursor()
        sql = """
        SELECT EXECUTION_ID,
               USERNAME,
               EXECUTION_DATE,
               QUERY,
               HOST
        FROM P4S_FUSION_EXECUTION_HISTORY
        WHERE USERNAME = :1
        ORDER BY EXECUTION_DATE DESC
        """
        cursor.execute(sql, [username])
        
        # Fetch up to 100 recent executions
        rows = cursor.fetchmany(100)
        
        history = []
        for row in rows:
            history.append({
                "EXECUTION_ID": row[0],
                "USERNAME": row[1],
                "EXECUTION_DATE": row[2].isoformat() if row[2] else None,
                "QUERY": row[3],
                "HOST": row[4]
            })
        
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch execution history: {str(e)}")
    finally:
        cursor.close()
        conn.close()
