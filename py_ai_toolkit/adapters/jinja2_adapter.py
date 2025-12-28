from typing import Any, Optional

from jinja2 import Environment

from py_ai_toolkit.core.domain.errors import FormatterAdapterError
from py_ai_toolkit.core.ports import FormatterPort


class Jinja2Adapter(FormatterPort):
    """
    Jinja2 implementation of the formatter port.
    Supports only Markdown files.
    """

    def __init__(self):
        self.env = Environment()

    def _load_prompt(self, path: str | None = None) -> str:
        if not path:
            raise FormatterAdapterError("Path is required")
        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    def render(
        self,
        path: str | None = None,
        prompt: str | None = None,
        input: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Render a Markdown template from a path with variables.

        Args:
            path (str | None): The directory path where the file is located
            prompt (str | None): The prompt to render
            input (Optional[dict[str, Any]]): Variables to pass to the template
        """
        if not path and not prompt:
            raise FormatterAdapterError("Either path or prompt must be provided")
        base_prompt = prompt or self._load_prompt(path)
        template = self.env.from_string(base_prompt)
        return template.render(**(input or {}))
