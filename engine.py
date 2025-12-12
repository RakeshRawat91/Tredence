# app/engine.py
import asyncio
import uuid
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import GraphSpec, RunState, NodeResult

# In-memory stores (replace with DB if needed)
GRAPHS: Dict[str, GraphSpec] = {}
RUNS: Dict[str, RunState] = {}

class WorkflowEngine:
    def __init__(self):
        self.graphs = GRAPHS
        self.runs = RUNS

    def create_graph(self, spec: GraphSpec) -> str:
        graph_id = str(uuid.uuid4())
        self.graphs[graph_id] = spec
        return graph_id

    async def _call_node(self, node_fn: Callable, state: dict) -> Tuple[dict, NodeResult]:
        """Call node function (sync or async). Node should accept state and tools registry if needed."""
        if inspect.iscoroutinefunction(node_fn):
            res = await node_fn(state)
        else:
            # allow CPU-bound quick functions to run synchronously
            res = node_fn(state)
            if inspect.iscoroutine(res):
                res = await res
        # Expect node to return either dict (modified state) or NodeResult
        if isinstance(res, NodeResult):
            return res.state, res
        elif isinstance(res, dict):
            nr = NodeResult(state=res, log=f"node returned dict")
            return res, nr
        else:
            # fallback: no change
            nr = NodeResult(state=state, log=f"node returned unexpected type; no change")
            return state, nr

    async def run_graph(self, graph_id: str, initial_state: dict, run_in_background: bool = False) -> str:
        if graph_id not in self.graphs:
            raise KeyError("graph not found")

        spec = self.graphs[graph_id]
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            graph_id=graph_id,
            state=initial_state.copy(),
            logs=[],
            current_node=None,
            finished=False,
            error=None
        )
        self.runs[run_id] = run_state

        async def _runner():
            try:
                await self._execute(spec, run_state)
            except Exception as e:
                run_state.error = str(e)
                run_state.finished = True

        if run_in_background:
            asyncio.create_task(_runner())
        else:
            await _runner()

        return run_id

    async def _execute(self, spec: GraphSpec, run_state: RunState):
        nodes = spec.nodes  # mapping name -> callable
        edges = spec.edges  # mapping name -> next (or branching dict)
        state = run_state.state
        start = spec.start_node
        if not start:
            raise ValueError("graph has no start_node")

        current = start
        visited = 0
        max_steps = spec.max_steps or 1000

        while current is not None:
            if visited >= max_steps:
                run_state.logs.append("max steps reached; aborting")
                break
            visited += 1
            run_state.current_node = current
            node_fn = nodes.get(current)
            run_state.logs.append(f"running {current}")
            # call the node
            new_state, node_res = await self._call_node(node_fn, state)
            # append node log if present
            if node_res.log:
                run_state.logs.append(f"{current}: {node_res.log}")

            # update shared state
            state.update(new_state)
            run_state.state = state.copy()

            # branching: node_res may contain 'next_node' OR edges mapping may define
            next_node = None
            if node_res.next_node:
                next_node = node_res.next_node
            else:
                # edges can be:
                #  - simple str for next node
                #  - dict of {"cond": lambda state: "nodeA", "else": "nodeB"}
                edge = edges.get(current)
                if isinstance(edge, str) or edge is None:
                    next_node = edge
                elif isinstance(edge, dict):
                    # support conditional mapping: {"if": lambda state: (True/False), "true": "n1", "false": "n2"}
                    cond = edge.get("cond")
                    if callable(cond):
                        try:
                            cond_res = cond(state)
                            if inspect.iscoroutine(cond_res):
                                cond_res = await cond_res
                        except Exception:
                            cond_res = False
                        next_node = edge.get("true") if cond_res else edge.get("false")
                    else:
                        # key-based branching by state field: {"field":"score","op":">=","value":10,"true":"n1","false":"n2"}
                        if "field" in edge:
                            val = state.get(edge["field"])
                            op = edge.get("op", "==")
                            cmp_val = edge.get("value")
                            if op == ">=":
                                take_true = (val is not None and val >= cmp_val)
                            elif op == "<=":
                                take_true = (val is not None and val <= cmp_val)
                            elif op == ">":
                                take_true = (val is not None and val > cmp_val)
                            elif op == "<":
                                take_true = (val is not None and val < cmp_val)
                            else:
                                take_true = (val == cmp_val)
                            next_node = edge.get("true") if take_true else edge.get("false")
                        else:
                            next_node = edge.get("next")
                else:
                    next_node = None

            run_state.logs.append(f"{current} -> next: {next_node}")
            current = next_node

        run_state.finished = True
        run_state.current_node = None
