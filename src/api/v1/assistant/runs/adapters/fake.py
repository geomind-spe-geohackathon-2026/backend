import geomind as gd
import geomind.types as gd_types

MODEL = "scripted/model"
USAGE = gd_types.Usage(input_tokens=120, output_tokens=40, cost=0.001)
ROUTE = '{"kind": "loop", "loop": "tool", "agent": "analyst"}'
ANSWER = "The scripted assistant finished after your approval."


def says(text: str) -> gd_types.Completion:
    return gd_types.Completion(text=text, usage=USAGE, model=MODEL)


def asks_to_list() -> gd_types.Completion:
    call = gd_types.ToolCall(id="scripted-list", name="list_plants", input={})
    return gd_types.Completion(
        text="I will look at the project's plants.",
        tool_calls=(call,),
        usage=USAGE,
        model=MODEL,
    )


def asks_to_save() -> gd_types.Completion:
    call = gd_types.ToolCall(
        id="scripted-call",
        name="save_profile",
        input={
            "name": "scripted",
            "values": [1.0],
            "unit": "MW",
            "start": "2026-01-01T00:00:00Z",
            "step": {"value": 1, "unit": "d"},
            "service": "heating",
        },
    )
    return gd_types.Completion(
        text="I will save a profile.",
        tool_calls=(call,),
        usage=USAGE,
        model=MODEL,
    )


def scripted_llm(resumed: bool) -> gd.providers.FakeLLM:
    """Return the test LLM that plays one run: route, list the plants, ask to write, then answer.

    The first process plays the route and the write, which pauses for approval; the
    process that resumes plays the answer. Only ``ASSISTANT_LLM=fake`` selects it.
    """
    if resumed:
        return gd.providers.FakeLLM([says(ANSWER)])
    return gd.providers.FakeLLM([says(ROUTE), asks_to_list(), asks_to_save()])
