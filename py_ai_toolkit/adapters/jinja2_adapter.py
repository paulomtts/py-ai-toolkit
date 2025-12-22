from typing import Any, Optional

from jinja2 import Environment

from py_ai_toolkit.core.ports import FormatterPort


class Jinja2Adapter(FormatterPort):
    """
    Jinja2 implementation of the formatter port.
    Supports only Markdown files.
    """

    def __init__(self):
        self.env = Environment()

    def _load_prompt(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    def render(
        self,
        path: str,
        input: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Render a Markdown template from a path with variables.

        Args:
            path: The directory path where the file is located
            input: Variables to pass to the template
        """
        base_prompt = self._load_prompt(path)
        template = self.env.from_string(base_prompt)
        return template.render(**(input or {}))
