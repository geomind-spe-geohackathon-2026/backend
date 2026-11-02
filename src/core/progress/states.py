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


def build_progress(facts: ProjectFacts) -> Progress:
    """Compute the five steps of a project; nothing here is stored."""
    return Progress(
        case=case_step(facts.case_version, facts.case_missing),
        plant=version_step(facts.plant_version),
        study=study_step(facts.studies),
        results=results_step(facts.results),
        report=report_step(facts),
    )
