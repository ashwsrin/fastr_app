import os
import json
from pydantic import BaseModel, Field
from typing import TypedDict, Annotated, Sequence, Literal, Any, List, Optional, Dict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool, BaseTool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
import db_tools

# --- OCI Serializers (Copied from talk2data/app/agent.py) ---

def _get_item_attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

def _infer_tool_name_from_args(args: dict, tools_list: List[BaseTool]) -> str:
    if not args or not isinstance(args, dict) or not tools_list:
        return ""
    arg_keys = set(args.keys())
    best_name = ""
    best_score = 0
    for t in tools_list:
        schema = getattr(t, "args_schema", None)
        if schema is None:
            continue
        try:
            if isinstance(schema, dict):
                schema_dict = schema
            else:
                js = getattr(schema, "model_json_schema", None)
                schema_dict = js() if callable(js) else {}
        except Exception:
            schema_dict = {}
        props = schema_dict.get("properties") or {}
        schema_keys = set(props.keys())
        if not schema_keys:
            continue
        overlap = len(arg_keys & schema_keys)
        if overlap > best_score and overlap >= len(arg_keys) * 0.5:
            best_score = overlap
            best_name = getattr(t, "name", "") or ""
    return best_name or ""

def _collect_function_call_items(output: Any) -> List[dict]:
    if output is None:
        return []
    if isinstance(output, dict) and "data" in output:
        output = output.get("data") or []
    if not isinstance(output, list):
        return []
    items: List[Any] = []
    for item in output:
        if _get_item_attr(item, "type") == "function_call":
            items.append(item)
        elif _get_item_attr(item, "type") == "message":
            content = _get_item_attr(item, "content")
            if isinstance(content, list):
                for sub in content:
                    if _get_item_attr(sub, "type") == "function_call":
                        items.append(sub)
    tool_calls = []
    for item in items:
        name = _get_item_attr(item, "name") or ""
        arguments = _get_item_attr(item, "arguments")
        if arguments is None:
            arguments = _get_item_attr(item, "input")
        call_id = _get_item_attr(item, "id") or _get_item_attr(item, "call_id") or ""
        try:
            if isinstance(arguments, str):
                args = json.loads(arguments) if arguments.strip() else {}
            elif isinstance(arguments, dict):
                args = arguments
            else:
                args = {}
        except json.JSONDecodeError:
            args = {}
        tool_calls.append({"id": call_id, "name": name, "args": args})
    return tool_calls

def oci_response_to_aimessage(response: Any) -> AIMessage:
    output_text = getattr(response, "output_text", None)
    if callable(output_text):
        output_text = output_text()
    content = (output_text or "") if isinstance(output_text, str) else ""
    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")
    output = output or []
    tool_calls = _collect_function_call_items(output)
    return AIMessage(content=content, tool_calls=tool_calls if tool_calls else [])

def messages_to_oci_input(messages: Sequence[BaseMessage], tools: Optional[List[BaseTool]] = None) -> List[dict]:
    input_list: List[dict] = []
    skipped_call_ids: set = set()

    for msg in messages:
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, list):
                oci_parts: List[dict] = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    part_type = part.get("type")
                    if part_type == "text":
                        oci_parts.append({"type": "input_text", "text": part.get("text", "") or ""})
                    elif part_type == "image_url":
                        image_url_obj = part.get("image_url")
                        url = image_url_obj.get("url", "") if isinstance(image_url_obj, dict) else (image_url_obj or "")
                        if url and isinstance(url, str) and url.strip():
                            oci_parts.append({"type": "input_image", "image_url": url.strip(), "detail": "high"})
                    elif part_type == "file_url":
                        file_url = part.get("file_url")
                        if file_url and isinstance(file_url, str) and file_url.strip():
                            file_name = part.get("file_name") or "document.pdf"
                            url_stripped = file_url.strip()
                            if url_stripped.startswith("data:"):
                                oci_parts.append({"type": "input_file", "filename": file_name, "file_data": url_stripped})
                            else:
                                oci_parts.append({"type": "input_file", "file_url": url_stripped})
                if oci_parts:
                    input_list.append({"role": "user", "content": oci_parts})
                else:
                    input_list.append({"role": "user", "content": ""})
            else:
                content_str = content if isinstance(content, str) else str(content or "")
                input_list.append({"role": "user", "content": content_str})
        elif isinstance(msg, AIMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                input_list.append({"role": "assistant", "content": content})
            else:
                if content:
                    input_list.append({"role": "assistant", "content": content})
                for tc in tool_calls:
                    name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                    name = (name or "").strip()
                    args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    if not isinstance(args, dict):
                        try:
                            args = json.loads(args) if isinstance(args, str) else {}
                        except json.JSONDecodeError:
                            args = {}
                    if not name and tools:
                        name = _infer_tool_name_from_args(args, tools)
                    call_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                    if not name:
                        if call_id:
                            skipped_call_ids.add(str(call_id))
                            c = str(call_id)
                            if c.startswith("fc_"):
                                skipped_call_ids.add(c[3:])
                            else:
                                skipped_call_ids.add(f"fc_{c}")
                        continue
                    fc_id = f"fc_{call_id}" if call_id and not str(call_id).startswith("fc_") else (call_id or "fc_")
                    input_list.append({
                        "type": "function_call",
                        "id": fc_id,
                        "name": name,
                        "arguments": json.dumps(args) if isinstance(args, dict) else str(args or "{}"),
                        "call_id": call_id,
                    })
        elif isinstance(msg, ToolMessage):
            call_id = getattr(msg, "tool_call_id", None) or ""
            if call_id and str(call_id) in skipped_call_ids:
                continue
            content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
            _max_tool_output_chars = 20000
            if len(content) > _max_tool_output_chars:
                content = content[:_max_tool_output_chars] + "\n\n[Output truncated for length.]"
            fc_id = f"fc_{call_id}" if call_id and not str(call_id).startswith("fc_") else (call_id or "fc_")
            input_list.append({
                "type": "function_call_output",
                "id": fc_id,
                "call_id": call_id,
                "output": content,
            })
        else:
            content = getattr(msg, "content", str(msg))
            input_list.append({"role": "user", "content": str(content)})
    return input_list

_OCI_PARAMS_DISALLOWED_TOP_LEVEL = frozenset({"oneOf", "anyOf", "allOf", "enum", "not"})

def _ensure_no_any_in_schema(params: dict) -> dict:
    return params

def _normalize_oci_parameters_schema(params: dict) -> dict:
    if not isinstance(params, dict):
        return {"type": "object", "properties": {}}
    params = _ensure_no_any_in_schema(params.copy())
    for key in _OCI_PARAMS_DISALLOWED_TOP_LEVEL:
        params.pop(key, None)
    if params.get("type") not in ("object",):
        params["type"] = "object"
    if "properties" not in params or not isinstance(params.get("properties"), dict):
        params["properties"] = {}
    return params

def tools_to_oci_functions(tools: List[BaseTool]) -> List[dict]:
    oci_tools: List[dict] = []
    for t in tools:
        name = getattr(t, "name", None) or "unknown"
        description = getattr(t, "description", None) or ""
        try:
            schema = t.get_input_schema() if hasattr(t, "get_input_schema") else {}
            if hasattr(schema, "model_json_schema"):
                params = schema.model_json_schema()
            elif isinstance(schema, dict):
                params = schema
            else:
                params = {"type": "object", "properties": {}}
            params = _normalize_oci_parameters_schema(params)
        except Exception:
            params = {"type": "object", "properties": {}}
        oci_tools.append({
            "type": "function",
            "name": name,
            "description": description or name,
            "parameters": params,
        })
    return oci_tools

# --- End OCI Serializers ---
# We will use the existing OCI OpenAI compatibility layer from Talk2Data if possible, 
# or standard langchain_community.chat_models imports if needed.
# Since the user pointed to their specific agent implementation, we'll try to mirror 
# the environment setup for OCI GenAI.

# Minimal placeholder for OCI OpenAI wrapper to avoid complex dependencies
# We assume the user has `oci` installed and configuring `~/.oci/config` is handled by the OCI SDK automatically.
try:
    from oci_openai import OciOpenAI, OciUserPrincipalAuth
    HAS_OCI_OPENAI = True
except ImportError:
    HAS_OCI_OPENAI = False
    
import json

# Define the state for the LangGraph
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Define Tools
@tool
def discover_tables_tool(search_query: str, pillar: str = None, module: str = None) -> str:
    """
    Search for Fusion tables based on a natural language query.
    Returns a list of matching tables and their descriptions.
    """
    try:
        conn = db_tools.get_db_connection()
        try:
            results = db_tools.discover_tables(conn, search_query=search_query, pillar=pillar, module=module, limit=5)
            if not results:
                return "No tables found matching that description."
            return json.dumps(results, indent=2)
        finally:
            conn.close()
    except Exception as e:
        return f"Error discovering tables: {str(e)}"

@tool
def get_table_metadata_tool(table_name: str) -> str:
    """
    Retrieve the full schema and column descriptions for a specific Fusion table.
    Always call this BEFORE attempting to write SQL against a table you are not 100% familiar with.
    """
    try:
        conn = db_tools.get_db_connection()
        try:
            schema = db_tools.get_table_metadata(conn, table_name)
            if not schema:
                return f"Table {table_name} not found."
            return schema
        finally:
            conn.close()
    except Exception as e:
        return f"Error fetching metadata: {str(e)}"

tools = [discover_tables_tool, get_table_metadata_tool]

# System Prompt
SYSTEM_PROMPT = """
You are FASTR, an AI Oracle Fusion SQL expert. Your goal is to help the user discover tables, understand their schema, and write accurate SQL queries.

You have access to tools:
1. `discover_tables_tool`: Use this when the user asks finding tables related to a business concept.
2. `get_table_metadata_tool`: Use this to investigate the exact column names and definitions of a table BEFORE writing SQL. 

Format your final response strictly as a JSON object with the following structure:
{
  "type": "chat" | "table_discovery" | "sql_generation",
  "content": "Your markdown formatted message to the user.",
  "sql": "Only include this field if type is sql_generation, containing the raw SQL code."
}
"""

def create_agent_graph():
    # If OCI OpenAI wrapper is available, use it. Otherwise, we fallback to a mock for now until the user imports their specific module.
    # In a real environment, we would initialize the LLM here.
    # For this skeleton to remain runnable without crashing if `oci_openai` isn't in PYTHONPATH:
    
    if HAS_OCI_OPENAI:
        # Assuming the user's config structure from their reference file
        llm = OciOpenAI(
            region=os.getenv("OCI_REGION", "us-chicago-1"), 
            auth=OciUserPrincipalAuth(config_file=os.path.expanduser("~/.oci/config"), profile_name="DEFAULT"),
            compartment_id=os.getenv("OCI_COMPARTMENT_ID", "")
        )
    else:
        # Fallback pseudo-LLM if library not found so fastapi doesn't crash on boot
        # We will log a warning.
        class MockLLM:
            def invoke(self, messages):
                return AIMessage(content=json.dumps({"type": "chat", "content": "OCI GenAI library not found. Please ensure oci_openai is in the Python path."}))
        llm_with_tools = MockLLM()

    # Define Node functions
    def call_model(state: AgentState):
        messages = state['messages']
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        
        if HAS_OCI_OPENAI:
            # We must convert tools to OCI format and pass via kwargs since `bind_tools` isn't supported on this wrapper
            oci_messages = messages_to_oci_input(messages, tools)
            oci_tools = tools_to_oci_functions(tools)
            
            # Using the native OciOpenAI client method
            response = llm.responses.create(
                model="openai.gpt-4o",
                input=oci_messages,
                tools=oci_tools,
                temperature=0,
                max_output_tokens=2048,
                store=False
            )
            # Parse the OCI response shape into a LangChain AIMessage for the LangGraph state
            output_msg = oci_response_to_aimessage(response)
            
            return {"messages": [output_msg]}
        else:
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}

    def call_tools(state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        
        tool_messages = []
        if hasattr(last_message, 'tool_calls'):
            for tc in last_message.tool_calls:
                tool_name = tc["name"]
                args = tc["args"]
                
                # Execute mapped tool
                tool_result = ""
                if tool_name == "discover_tables_tool":
                    tool_result = discover_tables_tool.invoke(args)
                elif tool_name == "get_table_metadata_tool":
                    tool_result = get_table_metadata_tool.invoke(args)
                else:
                    tool_result = f"Unknown tool: {tool_name}"
                    
                tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tc["id"], name=tool_name))
                
        return {"messages": tool_messages}

    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        messages = state['messages']
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "__end__"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", call_tools)
    
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

agent_executor = create_agent_graph()

def generate_response(prompt: str, history: list = []) -> dict:
    """
    Main entry point for the FastAPI backend to interact with the agent.
    """
    messages = []
    for msg in history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content")))
            
    messages.append(HumanMessage(content=prompt))
    
    try:
        # Run graph
        final_state = agent_executor.invoke({"messages": messages})
        last_message = final_state["messages"][-1]
        
        # Try to parse the strictly requested JSON structure
        try:
            contentStr = last_message.content
            # Clean up potential markdown blocks the LLM might wrap the JSON in
            if contentStr.startswith("```json"):
                contentStr = contentStr[7:-3]
            elif contentStr.startswith("```"):
                contentStr = contentStr[3:-3]
                
            resp_dict = json.loads(contentStr.strip())
            return resp_dict
        except json.JSONDecodeError:
            # Fallback if LLM disobeys the JSON format rule
            return {
                "type": "chat",
                "content": last_message.content
            }
    except Exception as e:
        return {
            "type": "chat",
            "content": f"An error occurred in the agent workflow: {str(e)}"
        }
