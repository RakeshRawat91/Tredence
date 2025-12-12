# app/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uvicorn

from .engine import WorkflowEngine
from .models import GraphSpec, RunState, NodeResult
from .workflows import code_review  # import to ensure functions are defined
from . import tools

app = FastAPI(title="Mini Workflow Engine")

engine = WorkflowEngine()

# small helper to convert incoming JSON graph description (node names) into GraphSpec with callables
class CreateGraphPayload(BaseModel):
    nodes: Dict[str, str]  # node_name -> function_name (module dotted or local)
    edges: Dict[str, Any]
    start_node: str
    max_steps: Optional[int] = 1000

@app.post("/graph/create")
async def create_graph(payload: CreateGraphPayload):
    # resolve functions from name -> function object (simple mapping: functions in workflows.code_review)
    resolved_nodes = {}
    for name, fn_name in payload.nodes.items():
        # try to get attribute from workflows.code_review
        fn = getattr(code_review, fn_name, None)
        if fn is None:
            raise HTTPException(status_code=400, detail=f"function {fn_name} not found in code_review workflows")
        resolved_nodes[name] = fn
    spec = GraphSpec(nodes=resolved_nodes, edges=payload.edges, start_node=payload.start_node, max_steps=payload.max_steps)
    gid = engine.create_graph(spec)
    return {"graph_id": gid}

class RunPayload(BaseModel):
    graph_id: str
    initial_state: Dict[str, Any]
    run_in_background: Optional[bool] = False

@app.post("/graph/run")
async def run_graph(payload: RunPayload, background_tasks: BackgroundTasks):
    try:
        run_id = await engine.run_graph(payload.graph_id, payload.initial_state, run_in_background=payload.run_in_background)
    except KeyError:
        raise HTTPException(status_code=404, detail="graph not found")
    # if background, respond immediately with run_id
    run = engine.runs[run_id]
    return {"run_id": run_id, "state": run.state, "logs": run.logs, "finished": run.finished}

@app.get("/graph/state/{run_id}")
async def get_run_state(run_id: str):
    run = engine.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "state": run.state, "logs": run.logs, "current_node": run.current_node, "finished": run.finished, "error": run.error}

# simple endpoint to list registered tools
@app.get("/tools")
async def list_tools():
    return {"tools": list(tools.TOOLS.keys())}

# add a small example endpoint to create+run the example code-review graph quickly
@app.post("/example/run-code-review")
async def example_run_code_review(background_tasks: BackgroundTasks, payload: Dict = None):
    # build the graph programmatically
    nodes = {
        "extract": "extract_functions",
        "check_complexity": "check_complexity",
        "detect_issues": "detect_basic_issues",
        "suggest": "suggest_improvements",
        "check_done": "check_done"
    }
    # edges define flow and a loop back from check_done to check_complexity if needed
    edges = {
        "extract": "check_complexity",
        "check_complexity": "detect_issues",
        "detect_issues": "suggest",
        "suggest": "check_done",
        # check_done uses NodeResult.next_node to either finish or return to check_complexity
    }
    payload_graph = {"nodes": nodes, "edges": edges, "start_node": "extract", "max_steps": 50}
    create_payload = CreateGraphPayload(**payload_graph)
    resp = await create_graph(create_payload)
    graph_id = resp["graph_id"]
    initial_state = payload or {
        "code": "def foo(x):\n    # TODO: fix this\n    if x > 0:\n        print(x)\n\ndef bar(y):\n    for i in range(y):\n        if i % 2 == 0:\n            print(i)\n",
        "threshold": 85
    }
    run_id = await engine.run_graph(graph_id, initial_state, run_in_background=False)
    run = engine.runs[run_id]
    return {"graph_id": graph_id, "run_id": run_id, "state": run.state, "logs": run.logs, "finished": run.finished}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
