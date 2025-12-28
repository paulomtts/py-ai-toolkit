from py_ai_toolkit.adapters import InstructorAdapter, Jinja2Adapter, PydanticAdapter
from py_ai_toolkit.core.ports import FormatterPort, LLMPort, ModellerPort


def create_llm_client(
    model: str,
    embedding_model: str,
    api_key: str,
    base_url: str | None = None,
) -> LLMPort:
    """
    Factory function to create an LLMClient instance with default configuration.

    Args:
        model (Optional[str]): The model to use for completions. Defaults to LLM_MODEL env var.
        embedding_model (Optional[str]): The model to use for embeddings. Defaults to EMBEDDING_MODEL env var.

    Returns:
        LLMClient: Configured LLM client instance

    Raises:
        ValueError: If required configuration is missing
    """
    return InstructorAdapter(
        model=model,
        embedding_model=embedding_model,
        api_key=api_key,
        base_url=base_url,
    )


def create_prompt_formatter() -> FormatterPort:
    """
    Factory function to create a PromptFormatter instance.

    Returns:
        PromptFormatter: Configured prompt formatter instance
    """
    return Jinja2Adapter()


def create_model_handler() -> ModellerPort:
    """
    Factory function to create a ResponseModelService instance.

    Returns:
        ResponseModelService: Configured model handler instance
    """
    return PydanticAdapter()
