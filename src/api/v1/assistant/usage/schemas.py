from pydantic import BaseModel


class Usage(BaseModel):
    runs: int
    input_tokens: int
    output_tokens: int
    cost: float
