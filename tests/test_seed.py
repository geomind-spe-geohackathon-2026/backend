import importlib.util
from pathlib import Path

from src.core.gemini import study
from tests import design_inputs as inputs

SEED_SCRIPT = Path(__file__).parent.parent / "scripts" / "seed.py"


def seed_plant() -> dict:
    specification = importlib.util.spec_from_file_location("seed", SEED_SCRIPT)
    seed = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(seed)
    return seed.example_plant()


def test_the_seeded_plant_serves_heating_and_cooling_on_the_example_case() -> None:
    outcome = study.run(
        "run",
        "s",
        {},
        seed_plant(),
        inputs.case_content(),
        inputs.case_files(),
    )

    assert outcome["report"]["heat_delivered"]["value"] > 0
    assert outcome["report"]["cold_delivered"]["value"] > 0
