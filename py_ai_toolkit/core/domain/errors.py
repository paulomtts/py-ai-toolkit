class WorkflowError(Exception):
    """
    Exception raised when an error occurs in the workflow.
    """


class LLMAdapterError(Exception):
    """
    Exception raised when an error occurs in the LLM adapter.
    """


class FormatterAdapterError(Exception):
    """
    Exception raised when an error occurs in the formatter adapter.
    """
