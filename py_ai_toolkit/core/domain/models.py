from pydantic import BaseModel, Field


class BaseIssue(BaseModel):
    is_valid: bool = Field(description="Whether the output passes the test")
    reasoning: str = Field(
        description="A short sentence, explaining the reasoning behind the test result"
    )
