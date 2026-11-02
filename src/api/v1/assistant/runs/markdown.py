import json
from typing import Any


def fenced(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    return f"```\n{text}\n```"


def llm_section(call: dict[str, Any]) -> list[str]:
    lines = [
        f"- LLM call, model `{call['model']}`: {call['input_tokens']} in, "
        f"{call['output_tokens']} out, cost {call['cost']:.4g}, "
        f"{call['duration']:.3f} s",
    ]
    if call["answer"]:
        lines += ["", call["answer"]]
    return lines


def tool_section(call: dict[str, Any]) -> list[str]:
    failed = " (error)" if call.get("error") else ""
    return [
        f"- Tool `{call['tool']}`{failed}, {call['duration']:.3f} s",
        "",
        "Input:",
        fenced(call["input"]),
        "",
        "Output:",
        fenced(call["output"]),
    ]


def step_section(step: dict[str, Any]) -> list[str]:
    parent = "" if step["parent"] is None else f", delegated from step {step['parent']}"
    lines = ["", f"## Step {step['index']}: {step['agent']}{parent}", ""]
    for call in step["llm_calls"]:
        lines += [*llm_section(call), ""]
    for call in step["tool_calls"]:
        lines += [*tool_section(call), ""]
    return lines


def to_markdown(log: dict[str, Any]) -> str:
    """Write a run log (``gd.runlog``) as Markdown."""
    run = log["run"]
    usage = run["usage"]
    lines = [
        f"# Run {run['id']}",
        "",
        f"- Status: {run['status']}",
        f"- Loop: {run['loop']}",
        f"- Started: {run['started']}",
        f"- Ended: {run['ended']}",
        f"- Tokens: {usage['input_tokens']} in, {usage['output_tokens']} out",
        f"- Cost: {usage['cost']}",
    ]
    for step in log["steps"]:
        lines += step_section(step)
    return "\n".join(lines).rstrip() + "\n"
