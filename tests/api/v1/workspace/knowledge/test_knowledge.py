import geomind as gd
import pytest

from tests.conftest import bearer
from tests.geomind_doubles import MEMORY

URL = "/api/v1/workspace/knowledge"
ENTRY = {
    "id": "drilling-cost",
    "item": "Drilling cost",
    "value": 1500,
    "unit": "EUR/m",
    "title": "Geothermal cost report",
    "publisher": "Agency",
    "year": 2024,
    "page": "12",
    "status": "verified",
    "price_year": 2024,
    "currency": "EUR",
}


@pytest.fixture
def memory(monkeypatch):
    monkeypatch.setattr(gd, "memory", MEMORY, raising=False)


async def admin_of(make_user):
    return await make_user("admin@example.com", role="admin")


async def test_an_admin_adds_a_cited_entry_and_anyone_reads_it(
    client, make_user, memory
) -> None:
    admin = await admin_of(make_user)
    member = await make_user()

    added = await client.post(URL, json=ENTRY, headers=bearer(admin))
    listed = await client.get(URL, params={"q": "drilling"}, headers=bearer(member))
    read = await client.get(f"{URL}/knowledge/drilling-cost", headers=bearer(member))

    assert added.status_code == 201, added.text
    body = added.json()
    assert body["value"] == 1500 and body["origin"] == "user"
    assert body["created_by"] == {"kind": "user", "id": str(admin.id)}
    assert [item["id"] for item in listed.json()["items"]] == ["drilling-cost"]
    assert read.json()["title"] == "Geothermal cost report"


async def test_an_entry_without_its_source_is_refused(
    client, make_user, memory
) -> None:
    admin = await admin_of(make_user)
    response = await client.post(
        URL, json={**ENTRY, "title": None, "page": None}, headers=bearer(admin)
    )
    assert response.status_code == 422
    assert "title" in response.json()["error"]["details"]["fields"]["entry"]


async def test_a_member_cannot_write(client, make_user, memory) -> None:
    member = await make_user()
    response = await client.post(URL, json=ENTRY, headers=bearer(member))
    assert response.status_code == 403


async def test_an_entry_is_changed_and_checked_again(client, make_user, memory) -> None:
    admin = await admin_of(make_user)
    await client.post(URL, json=ENTRY, headers=bearer(admin))

    changed = await client.patch(
        f"{URL}/knowledge/drilling-cost", json={"value": 1600}, headers=bearer(admin)
    )
    broken = await client.patch(
        f"{URL}/knowledge/drilling-cost", json={"title": None}, headers=bearer(admin)
    )

    assert changed.json()["value"] == 1600
    assert broken.status_code == 422


async def test_an_entry_is_deleted(client, make_user, memory) -> None:
    admin = await admin_of(make_user)
    await client.post(URL, json=ENTRY, headers=bearer(admin))

    deleted = await client.delete(
        f"{URL}/knowledge/drilling-cost", headers=bearer(admin)
    )
    missing = await client.get(f"{URL}/knowledge/drilling-cost", headers=bearer(admin))

    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "entry_not_found"


async def test_a_catalogue_csv_is_imported_row_by_row(
    client, make_user, memory
) -> None:
    admin = await admin_of(make_user)
    csv = (
        "id,item,value,unit,source,publisher,year,page,status\n"
        "pump,Pump cost,200,EUR/kW,Catalogue,Maker,2023,4,verified\n"
        "bad,No source,1,EUR,,,,,verified\n"
    )

    response = await client.post(
        f"{URL}/import", files={"file": ("costs.csv", csv)}, headers=bearer(admin)
    )

    report = response.json()
    assert response.status_code == 200, response.text
    assert (report["added"], report["replaced"]) == (1, 0)
    assert [problem["row"] for problem in report["errors"]] == [3]


async def test_without_geomind_memory_writes_say_not_implemented(
    client, make_user, monkeypatch
) -> None:
    monkeypatch.delattr(gd, "memory", raising=False)
    admin = await admin_of(make_user)

    response = await client.post(URL, json=ENTRY, headers=bearer(admin))
    settings = await client.get(f"{URL}/settings", headers=bearer(admin))

    assert response.status_code == 501
    assert settings.json()["available"] is False
    assert settings.json()["sections"] == ["knowledge", "experience"]
