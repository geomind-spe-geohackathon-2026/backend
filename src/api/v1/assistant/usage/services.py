from src.api.v1.assistant.usage import schemas
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.run import RunRepository


async def read_usage(project: Project, runs: RunRepository) -> schemas.Usage:
    count, input_tokens, output_tokens, cost = await runs.usage(project.id)
    return schemas.Usage(
        runs=count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
    )
