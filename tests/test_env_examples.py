from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SECONDS = ("GEOMIND_RETRY_DELAY", "GEOMIND_MCP_TIMEOUT")


@pytest.mark.parametrize("name", [".env.example", ".env.dev.example"])
def test_geomind_durations_are_plain_seconds(name: str) -> None:
    lines = (ROOT / name).read_text().splitlines()
    values = dict(line.split("=", 1) for line in lines if "=" in line)
    for setting in SECONDS:
        float(values[setting])
