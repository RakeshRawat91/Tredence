# app/models.py
from typing import Any, Dict, Optional
from pydantic import BaseModel

class NodeResult(BaseModel):
    state: Dict[str, Any]
    log: Optional[str] = None
    next_node: Optional[str] = None

class GraphSpec(BaseModel):
    # nodes mapping name -> callable (we'll store callables at runtime, but spec holds metadata)
    nodes: Dict[str, Any]  # at runtime stores functions
    edges: Dict[str, Any]  # mapping name -> next or branching dict
    start_node: str
    max_steps: Optional[int] = 1000

class RunState(BaseModel):
    run_id: str
    graph_id: str
    state: Dict[str, Any]
    logs: list
    current_node: Optional[str] = None
    finished: bool = False
    error: Optional[str] = None
