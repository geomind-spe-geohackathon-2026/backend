from src.api.v1.assistant.runs import markdown


def test_a_duration_is_written_with_three_decimals() -> None:
    call = {
        "model": "m",
        "input_tokens": 10,
        "output_tokens": 5,
        "cost": 0.0012345678,
        "duration": 0.0070560850435867906,
        "answer": "",
    }

    line = markdown.llm_section(call)[0]

    assert line.endswith("cost 0.001235, 0.007 s")
    assert "0.0070560850435867906" not in line


def test_a_tool_duration_is_written_with_three_decimals() -> None:
    call = {"tool": "t", "duration": 1.23456789, "input": {}, "output": "x"}

    assert markdown.tool_section(call)[0] == "- Tool `t`, 1.235 s"
