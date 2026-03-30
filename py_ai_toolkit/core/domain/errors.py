class WorkflowError(Exception):
    """
    Exception raised when an error occurs in the workflow.
    """

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class LLMAdapterError(Exception):
    """
    Exception raised when an error occurs in the LLM adapter.
    """

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class FormatterAdapterError(Exception):
    """
    Exception raised when an error occurs in the formatter adapter.
    """

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message
