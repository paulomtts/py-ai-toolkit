from pydantic import BaseModel, Field


class ValidationTest(BaseModel):
    is_valid: bool = Field(description="Whether the output passes the test")
    reasoning: str = Field(
        description="A short sentence, explaining the reasoning behind the test result"
    )


class BaseValidation(BaseModel):
    validations: list[ValidationTest] = Field(description="A list of tests")

    @property
    def valid(self) -> bool:
        return all(test.is_valid for test in self.validations)
