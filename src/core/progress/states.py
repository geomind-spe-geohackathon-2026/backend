from src.core.clients.postgres.repositories.progress import ProjectFacts
from src.core.progress.schemas import Progress, ProgressStep


def case_step(version: int | None, missing: int) -> ProgressStep:
    """A case with values gemini lists as missing is incomplete, not ready."""
    if version is not None and missing:
        return ProgressStep(
            state="incomplete", label=f"Version {version}, {missing} missing"
        )
    return version_step(version)


def version_step(version: int | None) -> ProgressStep:
    if version is None:
        return ProgressStep(state="empty", label="Not started")
    return ProgressStep(state="ready", label=f"Version {version}")


def plant_step(facts: ProjectFacts) -> ProgressStep:
    """The plant: its saved version, else whether designs exist only in studies or results.

    Since QA-237 an assistant run saves no plant version, so a project with agent studies and
    results showed the plant "Not started" (QA-328). Such a plant is ``incomplete``: designs
    exist, none is saved as the project plant.
    """
    if facts.plant_version is not None:
        return version_step(facts.plant_version)
    if facts.results or sum(facts.studies.values()):
        return ProgressStep(state="incomplete", label="Not saved: designs only in results")
    return version_step(None)


def study_step(counts: dict[str, int]) -> ProgressStep:
    """Running beats done, done beats blocked; any other study leaves it empty."""
    active = counts.get("queued", 0) + counts.get("running", 0)
    if active:
        return ProgressStep(state="running", label=f"{active} running")
    if counts.get("done", 0):
        return ProgressStep(state="done", label=f"{counts['done']} done")
    if counts.get("blocked", 0):
        return ProgressStep(state="incomplete", label=f"{counts['blocked']} blocked")
    return ProgressStep(state="empty", label="No studies")


def results_step(count: int) -> ProgressStep:
    if count == 0:
        return ProgressStep(state="empty", label="No results")
    return ProgressStep(state="done", label=f"{count} results")


def report_step(facts: ProjectFacts) -> ProgressStep:
    if facts.reported:
        return ProgressStep(state="done", label="Exported")
    if facts.results:
        return ProgressStep(state="ready", label="Draft")
    return ProgressStep(state="empty", label="Not started")


def economics_step(has_economics: bool) -> ProgressStep:
    """``done`` when the latest case has an ``economics`` section, else ``empty`` (QA-194)."""
    if has_economics:
        return ProgressStep(state="done", label="Set")
    return ProgressStep(state="empty", label="Not set")


def build_progress(facts: ProjectFacts, economics: bool | None = None) -> Progress:
    """Compute the steps of a project; nothing here is stored.

    ``economics`` says whether the latest case has economics; ``None`` leaves the item out.
    """
    return Progress(
        case=case_step(facts.case_version, facts.case_missing),
        plant=plant_step(facts),
        study=study_step(facts.studies),
        results=results_step(facts.results),
        report=report_step(facts),
        economics=None if economics is None else economics_step(economics),
    )
