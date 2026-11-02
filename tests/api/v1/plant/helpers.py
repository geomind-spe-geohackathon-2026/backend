from typing import Any

import gemini as gm

from tests.plants import example_plant

FLOWSHEET = "/api/v1/plant/flowsheet"
PARAMETERS = "/api/v1/plant/parameters"


def template_name() -> str:
    return gm.plants.names("heating")[0]


def first_module(spec: dict[str, Any] | None = None) -> str:
    plant = gm.Plant.from_dict(spec or example_plant())
    return plant.to_dict(structure=True)["modules"].popitem()[0]


async def save_plant(client, headers, project, base=None, spec=None) -> dict[str, Any]:
    response = await client.post(
        FLOWSHEET,
        headers=headers,
        json={
            "project": str(project.id),
            "base": base,
            "note": "first",
            "spec": spec or example_plant(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
