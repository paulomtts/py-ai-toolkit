from typing import Annotated

import pytest
from dotenv import load_dotenv
from pydantic import Field

from py_ai_toolkit import Agent, Toolkit, ToolType, tool
from py_ai_toolkit.core.domain.schemas import LLMConfig

load_dotenv()


@pytest.mark.asyncio
async def test_agent_duplicate_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "source.txt"
    source.write_text("Hello, World!")
    dest = tmp_path / "dest.txt"

    @tool(tool_type=ToolType.GATHER)
    def read_file(
        filename: Annotated[
            str, Field(description="Name of the file to read (e.g. 'source.txt')")
        ],
    ) -> str:
        """Read contents of a file by filename."""
        return (tmp_path / filename).read_text()

    @tool(tool_type=ToolType.ACTION)
    def write_file(
        filename: Annotated[
            str, Field(description="Name of the file to write (e.g. 'dest.txt')")
        ],
        content: Annotated[str, Field(description="The content to write to the file")],
    ) -> bool:
        """Write content to a file by filename."""
        (tmp_path / filename).write_text(content)
        return True

    toolkit = Toolkit(main_model_config=LLMConfig())
    agent = Agent(toolkit=toolkit, tools=[read_file, write_file], max_iterations=15)

    goal = "Read the contents of 'source.txt' and write them to 'dest.txt'"
    await agent.run(goal)

    assert dest.exists()
    assert dest.read_text() == "Hello, World!\n"
