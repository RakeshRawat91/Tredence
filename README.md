# Tredence

# Mini Workflow Engine (AI Engineering Assignment)

## Overview
This is a small workflow/graph engine (FastAPI backend) supporting:
- Nodes as Python functions that read/modify shared state.
- State passed as a dict.
- Edges for transitions, plus basic conditional branching and looping.
- Tool registry: nodes can call helper tools.
- Example workflow: Code Review Mini-Agent (Option A) that loops until `quality_score >= threshold`.

## Files
- `app/main.py` - FastAPI app + endpoints
- `app/engine.py` - the workflow engine implementation
- `app/models.py` - Pydantic models for GraphSpec, RunState, NodeResult
- `app/tools.py` - tool registry and example tools
- `app/workflows/code_review.py` - nodes implementing the sample code review workflow

## Endpoints
- `POST /graph/create`
  - Input JSON:
    ```json
    {
      "nodes": {"extract": "extract_functions", "check_complexity": "check_complexity", ...},
      "edges": {"extract": "check_complexity", ...},
      "start_node": "extract"
    }
    ```
  - Returns: `{ "graph_id": "<uuid>" }`

- `POST /graph/run`
  - Input JSON:
    ```json
    { "graph_id": "...", "initial_state": {"code":"...","threshold":80}, "run_in_background": false }
    ```
  - Returns: `{ "run_id": "...", "state": {...}, "logs": [...], "finished": true/false }`

- `GET /graph/state/{run_id}`
  - Returns current state, logs, current node and finished flag.

- `GET /tools` - lists registered tools.

- `POST /example/run-code-review` - quick demo that creates & runs the sample code-review workflow.

## How to run
1. Create virtualenv and install:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
