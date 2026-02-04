import logging
import re
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

logger = logging.getLogger("PyAIToolkit")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def _extract_description(docstring: str | None) -> str:
    if not docstring:
        return ""
    first_paragraph = docstring.strip().split("\n\n")[0]
    return " ".join(line.strip() for line in first_paragraph.split("\n")).strip()


def _pascal_case(string: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", string).strip()
    return "".join(word.capitalize() for word in normalized.split())


def _is_basemodel_subclass(typ: Any) -> bool:
    try:
        return isinstance(typ, type) and issubclass(typ, BaseModel)
    except TypeError:
        return False


def _unwrap_annotated(hint: Any) -> Any:
    if get_origin(hint) is Annotated:
        return get_args(hint)[0]
    return hint
