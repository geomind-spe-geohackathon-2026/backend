import json

import geomind as gd
import geomind.types as gd_types

MODEL = "scripted/model"
USAGE = gd_types.Usage(input_tokens=120, output_tokens=40, cost=0.001)
ROUTE = '{"kind": "loop", "loop": "tool", "agent": "analyst"}'
ANSWER = "The scripted assistant finished after your approval."
SCENARIO = "demand profile"
SCENARIO_DAYS = 365
SCENARIO_START = "2027-01-01T00:00:00Z"
DEMO_ANSWER = "Demo mode: no model is connected, so this is a scripted reply."


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
            "values": [1.0] * SCENARIO_DAYS,
            "unit": "MW",
            "start": SCENARIO_START,
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


def scripted_llm(resumed: bool, message: str) -> gd.providers.FakeLLM:
    """Return the test LLM: a plain reply, or the scenario of a message that asks it.

    A message naming ``SCENARIO`` plays route, plants, write, which pauses for
    approval; the process that resumes plays the answer. Any other message gets a
    plain reply. Only ``ASSISTANT_LLM=fake`` selects it.
    """
    if resumed:
        return gd.providers.FakeLLM([says(ANSWER)])
    if SCENARIO in message.lower():
        return gd.providers.FakeLLM([says(ROUTE), asks_to_list(), asks_to_save()])
    reply = json.dumps({"kind": "answer", "answer": DEMO_ANSWER})
    return gd.providers.FakeLLM([says(reply)])
