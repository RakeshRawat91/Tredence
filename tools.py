# app/tools.py
from typing import Callable, Dict, Any

TOOLS: Dict[str, Callable] = {}

def register_tool(name: str):
    def decorator(fn):
        TOOLS[name] = fn
        return fn
    return decorator

# Example tools (rule-based helpers)
@register_tool("detect_smells")
def detect_smells(code: str) -> Dict[str, Any]:
    # trivial heuristic
    issues = 0
    if "TODO" in code:
        issues += 1
    if "print(" in code:
        issues += 1
    if len(code.splitlines()) > 200:
        issues += 2
    return {"issues": issues}

@register_tool("compute_complexity")
def compute_complexity(func_code: str) -> Dict[str, Any]:
    # naive function complexity: count branches keywords
    score = 1
    for kw in ("if ", "for ", "while ", "try:", "except"):
        score += func_code.count(kw)
    return {"complexity": score}
