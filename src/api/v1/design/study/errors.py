from src.core.errors import NotFoundError


class StudyNotFoundError(NotFoundError):
    code = "study_not_found"


class StructuresNotFoundError(NotFoundError):
    """The study is not an evolve study, or its result holds no structures."""

    code = "structures_not_found"


class StructurePlantNotStoredError(NotFoundError):
    """gemini stored no plant for this structure's design (only the best and the front have one)."""

    code = "structure_plant_not_stored"
