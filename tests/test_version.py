import re
from pathlib import Path

from src.version import VERSION

ROOT = Path(__file__).parents[1]


def test_the_version_is_semantic() -> None:
    assert re.fullmatch(r"[1-9]\d*\.\d+\.\d+", VERSION)


def test_the_changelog_and_the_contract_name_the_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text()
    contract = (ROOT / "docs" / "app-build" / "contracts.md").read_text()
    assert f"## [{VERSION}]" in changelog
    assert f"\nVersion {VERSION} (" in contract
