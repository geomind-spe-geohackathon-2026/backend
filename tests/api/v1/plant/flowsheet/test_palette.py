import gemini as gm

from tests.api.v1.plant.helpers import FLOWSHEET
from tests.conftest import bearer


async def test_palette_lists_gemini_modules_with_category_and_summary(
    client,
    make_user,
) -> None:
    user = await make_user()

    response = await client.get(f"{FLOWSHEET}/palette", headers=bearer(user))

    assert response.status_code == 200
    cards = response.json()
    assert {card["type"] for card in cards} == {
        gm.modules.get(name).__name__ for name in gm.modules.names()
    }
    assert all(card["category"] and card["summary"] for card in cards)


async def test_palette_filters_by_category(client, make_user) -> None:
    user = await make_user()
    category = gm.modules.categories()[0]

    response = await client.get(
        f"{FLOWSHEET}/palette",
        params={"category": category},
        headers=bearer(user),
    )

    assert {card["category"] for card in response.json()} == {category}


async def test_palette_refuses_an_unknown_category(client, make_user) -> None:
    user = await make_user()

    response = await client.get(
        f"{FLOWSHEET}/palette",
        params={"category": "zz"},
        headers=bearer(user),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "plant_invalid"


async def test_templates_are_gemini_plant_classes(client, make_user) -> None:
    user = await make_user()

    response = await client.get(f"{FLOWSHEET}/templates", headers=bearer(user))

    templates = response.json()
    assert [item["name"] for item in templates] == gm.plants.names()
    assert all(item["title"] == item["name"] for item in templates)
    assert all(item["description"] for item in templates)
    heating = gm.plants.get(gm.plants.names("heating")[0]).purpose
    assert heating in {item["purpose"] for item in templates}


async def test_palette_needs_a_token(client) -> None:
    response = await client.get(f"{FLOWSHEET}/palette")

    assert response.status_code == 401


async def test_ports_list_every_module_inlets_and_outlets(client, make_user) -> None:
    user = await make_user()

    response = await client.get(f"{FLOWSHEET}/ports", headers=bearer(user))

    assert response.status_code == 200
    cards = {card["type"]: card for card in response.json()}
    for name in gm.modules.names():
        description = gm.modules.get(name)().describe()
        card = cards[description["type"]]
        assert card["inlets"] == [
            {"port": port, "kind": declared["kind"]}
            for port, declared in description["inlets"].items()
        ]
        assert card["outlets"] == [
            {"port": port, "kind": declared["kind"]}
            for port, declared in description["outlets"].items()
        ]


async def test_ports_need_a_token(client) -> None:
    response = await client.get(f"{FLOWSHEET}/ports")

    assert response.status_code == 401
