# app/workflows/code_review.py
import asyncio
from typing import Dict
from ..models import NodeResult
from ..tools import TOOLS

# Example nodes for the code-review mini-agent

async def extract_functions(state: Dict) -> NodeResult:
    """
    Expects state['code'] to be a string.
    Produces state['functions'] = list of {'name':..., 'code':...}
    For demo, split by 'def ' occurrences (very naive).
    """
    code = state.get("code", "")
    funcs = []
    parts = code.split("\ndef ")
    if parts:
        # first part may be header code
        for i, p in enumerate(parts):
            if i == 0 and not p.strip().startswith("def "):
                # skip leading non-def part
                continue
            # restore leading def if it was removed
            text = (("def " + p) if not p.startswith("def ") else p).strip()
            # extract name naive
            name_line = text.splitlines()[0]
            name = name_line.split("(")[0].replace("def ", "").strip()
            funcs.append({"name": name, "code": text})
    await asyncio.sleep(0.05)
    return NodeResult(state={"functions": funcs}, log=f"extracted {len(funcs)} function(s)")

async def check_complexity(state: Dict) -> NodeResult:
    funcs = state.get("functions", [])
    results = []
    for f in funcs:
        res = TOOLS["compute_complexity"](f["code"])
        results.append({"name": f["name"], "complexity": res["complexity"]})
    await asyncio.sleep(0.05)
    return NodeResult(state={"complexity_report": results}, log="computed complexity")

async def detect_basic_issues(state: Dict) -> NodeResult:
    funcs = state.get("functions", [])
    total_issues = 0
    issues_detail = []
    for f in funcs:
        r = TOOLS["detect_smells"](f["code"])
        issues_detail.append({"name": f["name"], "issues": r["issues"]})
        total_issues += r["issues"]
    await asyncio.sleep(0.05)
    return NodeResult(state={"issues": {"total": total_issues, "detail": issues_detail}}, log=f"detected {total_issues} issues")

async def suggest_improvements(state: Dict) -> NodeResult:
    # a simple scoring: quality_score = 100 - complexity*5 - issues*10 (clamped)
    complexity_report = state.get("complexity_report", [])
    total_complexity = sum(item.get("complexity", 0) for item in complexity_report)
    issues = state.get("issues", {}).get("total", 0)
    quality_score = max(0, 100 - total_complexity * 5 - issues * 10)
    # suggest simple actions
    suggestions = []
    if issues > 0:
        suggestions.append("Fix TODOs and prints")
    if total_complexity > 10:
        suggestions.append("Refactor complex functions into smaller pieces")
    await asyncio.sleep(0.05)
    return NodeResult(state={"quality_score": quality_score, "suggestions": suggestions}, log=f"suggested improvements; score={quality_score}")

async def check_done(state: Dict) -> NodeResult:
    # intermediary node that decides if loop continues
    threshold = state.get("threshold", 80)
    quality = state.get("quality_score", 0)
    # if quality < threshold, we want to repeat analyze path else finish
    # we use NodeResult.next_node to control flow
    if quality >= threshold:
        return NodeResult(state={}, log=f"quality {quality} >= threshold {threshold}", next_node=None)
    else:
        # lower threshold slowly to avoid infinite loop in demo; or expect another iteration after developer fixes
        return NodeResult(state={}, log=f"quality {quality} < threshold {threshold}; looping", next_node="check_complexity")
