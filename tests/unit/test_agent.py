from typing import Annotated
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from py_ai_toolkit import Agent, AgentState, AgentStatus, ToolType, tool
from py_ai_toolkit.core.agent import (
    AgentDecision,
    CompactionSummary,
    ToolCallOutcome,
)
from py_ai_toolkit.core.context_pool import ContextPool


class TestAgentState:
    def test_default_status_is_running(self):
        state = AgentState(session_id="test", goal="test goal")
        assert state.status == AgentStatus.RUNNING

    def test_context_window_starts_empty(self):
        state = AgentState(session_id="test", goal="test goal")
        assert state.context_window == []

    def test_has_overflow_default_false(self):
        state = AgentState(session_id="test", goal="test goal")
        assert state.has_overflow is False

    def test_serialization(self):
        state = AgentState(
            session_id="abc123",
            goal="Complete the task",
            context_window=["step1", "step2"],
            status=AgentStatus.COMPLETE,
            has_overflow=True,
        )
        json_str = state.model_dump_json()
        restored = AgentState.model_validate_json(json_str)
        assert restored.session_id == "abc123"
        assert restored.goal == "Complete the task"
        assert restored.context_window == ["step1", "step2"]
        assert restored.status == AgentStatus.COMPLETE
        assert restored.has_overflow is True


class TestDecisionModels:
    def test_think_decision(self):
        decision = AgentDecision(
            action="think", reasoning="I need to analyze the problem"
        )
        assert decision.action == "think"
        assert decision.reasoning == "I need to analyze the problem"

    def test_use_tool_decision(self):
        decision = AgentDecision(action="use_tool", tool_name="read_file")
        assert decision.action == "use_tool"
        assert decision.tool_name == "read_file"

    def test_complete_decision(self):
        decision = AgentDecision(
            action="complete", summary="Task completed successfully"
        )
        assert decision.action == "complete"
        assert decision.summary == "Task completed successfully"


class TestToolCallOutcome:
    def test_success_outcome(self):
        outcome = ToolCallOutcome(
            tool_name="read_file",
            tool_args={"path": "/tmp/test.txt"},
            success=True,
            result="file contents",
        )
        assert outcome.success is True
        assert outcome.result == "file contents"
        assert outcome.error is None

    def test_error_outcome(self):
        outcome = ToolCallOutcome(
            tool_name="read_file",
            tool_args={"path": "/tmp/test.txt"},
            success=False,
            error="File not found",
        )
        assert outcome.success is False
        assert outcome.result is None
        assert outcome.error == "File not found"


class TestToolTypeEnum:
    def test_gather_tool(self):
        @tool(tool_type=ToolType.GATHER)
        def read_file(path: str) -> str:
            return "content"

        assert read_file.tool_type == ToolType.GATHER
        assert read_file.tool_type.value == "gather"

    def test_action_tool(self):
        @tool(tool_type=ToolType.ACTION)
        def write_file(path: str, content: str) -> bool:
            return True

        assert write_file.tool_type == ToolType.ACTION
        assert write_file.tool_type.value == "action"

    def test_default_tool_type_is_gather(self):
        @tool
        def search(query: str) -> list[str]:
            return []

        assert search.tool_type == ToolType.GATHER


class TestAgent:
    @pytest.fixture
    def sample_tools(self):
        @tool(tool_type=ToolType.GATHER)
        def read_file(path: Annotated[str, Field(description="Path to file")]) -> str:
            """Read contents of a file."""
            return "file content"

        @tool(tool_type=ToolType.ACTION)
        def write_file(
            path: Annotated[str, Field(description="Path to file")],
            content: Annotated[str, Field(description="Content to write")],
        ) -> bool:
            """Write content to a file."""
            return True

        return [read_file, write_file]

    @pytest.fixture
    def mock_toolkit(self):
        toolkit = MagicMock()
        toolkit.asend = AsyncMock()
        toolkit.embed = AsyncMock(return_value=[0.1] * 1536)
        return toolkit

    def test_init_creates_tool_dict(self, sample_tools, mock_toolkit):
        agent = Agent(toolkit=mock_toolkit, tools=sample_tools)
        assert "read_file" in agent.tools
        assert "write_file" in agent.tools

    def test_tool_type_classification(self, sample_tools, mock_toolkit):
        agent = Agent(toolkit=mock_toolkit, tools=sample_tools)
        assert agent.tools["read_file"].tool_type == ToolType.GATHER
        assert agent.tools["write_file"].tool_type == ToolType.ACTION

    def test_init_defaults(self, sample_tools, mock_toolkit):
        agent = Agent(toolkit=mock_toolkit, tools=sample_tools)
        assert agent.state is None
        assert agent.max_context_tokens == 80_000
        assert agent.compaction_threshold == 0.6
        assert agent.pool is None


class TestDecisionExecution:
    @pytest.fixture
    def agent(self, tmp_path):
        toolkit = MagicMock()
        toolkit.asend = AsyncMock()
        toolkit.embed = AsyncMock(return_value=[0.1] * 1536)

        @tool
        def dummy(x: str) -> str:
            return x

        agent = Agent(toolkit=toolkit, tools=[dummy])
        agent.state = AgentState(session_id="test123", goal="Test goal")

        with patch.object(agent, "_init_pool"):
            session_dir = tmp_path / ".agent_sessions" / "test123"
            session_dir.mkdir(parents=True)
            agent.pool = ContextPool(str(session_dir / "pool.db"))

        return agent

    @pytest.mark.asyncio
    async def test_think_adds_to_context(self, agent):
        decision = AgentDecision(action="think", reasoning="I should check the file")
        await agent._execute_decision(decision)
        assert "[Think]" in agent.state.context_window[-1]
        assert "I should check the file" in agent.state.context_window[-1]

    @pytest.mark.asyncio
    async def test_complete_sets_status(self, agent):
        decision = AgentDecision(action="complete", summary="Task done")
        await agent._execute_decision(decision)
        assert agent.state.status == AgentStatus.COMPLETE
        assert "[Complete]" in agent.state.context_window[-1]

    @pytest.mark.asyncio
    async def test_use_tool_adds_result_to_context(self, agent):
        class DummyParams(BaseModel):
            x: str

        agent.toolkit.asend.return_value = MagicMock(content=DummyParams(x="test"))

        decision = AgentDecision(action="use_tool", tool_name="dummy")
        await agent._execute_decision(decision)
        assert "[Tool: dummy]" in agent.state.context_window[-1]


class TestCompaction:
    @pytest.fixture
    def agent_with_context(self, tmp_path):
        toolkit = MagicMock()
        toolkit.asend = AsyncMock()
        toolkit.embed = AsyncMock(return_value=[0.1] * 1536)

        @tool
        def dummy(x: str) -> str:
            return x

        agent = Agent(toolkit=toolkit, tools=[dummy])
        agent.state = AgentState(session_id="test123", goal="Test goal")

        session_dir = tmp_path / ".agent_sessions" / "test123"
        session_dir.mkdir(parents=True)
        agent.pool = ContextPool(str(session_dir / "pool.db"))

        return agent

    def test_needs_compaction_false_when_under_limit(self, agent_with_context):
        agent_with_context.state.context_window = ["short"] * 10
        assert agent_with_context._needs_compaction() is False

    def test_needs_compaction_true_when_over_limit(self, agent_with_context):
        agent_with_context.max_context_tokens = 10
        agent_with_context.state.context_window = ["x" * 100] * 10
        assert agent_with_context._needs_compaction() is True

    @pytest.mark.asyncio
    async def test_compact_context_creates_summary(self, agent_with_context):
        agent_with_context.state.context_window = [f"item{i}" for i in range(10)]
        agent_with_context.toolkit.asend.return_value = MagicMock(
            content=CompactionSummary(
                summary="Summary of items",
                key_findings=["finding1"],
                references=["ref1"],
            )
        )

        await agent_with_context._compact_context()

        assert "[Compacted Summary]" in agent_with_context.state.context_window[0]
        assert agent_with_context.state.has_overflow is True


class TestContextPool:
    @pytest.fixture
    def pool(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return ContextPool(db_path=db_path, embedding_dim=4)

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, pool):
        chunk_id = await pool.store(
            text="Test chunk content",
            embedding=[0.1, 0.2, 0.3, 0.4],
            session_id="session1",
        )
        assert chunk_id is not None

        chunks = pool._get_session_chunks("session1")
        assert len(chunks) == 1
        assert chunks[0].text == "Test chunk content"

    @pytest.mark.asyncio
    async def test_hybrid_search(self, pool):
        await pool.store(
            text="Python programming language",
            embedding=[0.9, 0.1, 0.1, 0.1],
            session_id="session1",
        )
        await pool.store(
            text="JavaScript web development",
            embedding=[0.1, 0.9, 0.1, 0.1],
            session_id="session1",
        )

        results = await pool.hybrid_search(
            query_text="Python",
            query_embedding=[0.9, 0.1, 0.1, 0.1],
            session_id="session1",
            top_k=2,
        )

        assert len(results) == 2
        assert results[0].text == "Python programming language"

    @pytest.mark.asyncio
    async def test_session_isolation(self, pool):
        await pool.store(
            text="Session 1 content",
            embedding=[0.1, 0.2, 0.3, 0.4],
            session_id="session1",
        )
        await pool.store(
            text="Session 2 content",
            embedding=[0.5, 0.6, 0.7, 0.8],
            session_id="session2",
        )

        session1_chunks = pool._get_session_chunks("session1")
        session2_chunks = pool._get_session_chunks("session2")

        assert len(session1_chunks) == 1
        assert len(session2_chunks) == 1
        assert session1_chunks[0].text == "Session 1 content"
        assert session2_chunks[0].text == "Session 2 content"


class TestSessionManagement:
    @pytest.fixture
    def agent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        toolkit = MagicMock()
        toolkit.asend = AsyncMock()
        toolkit.embed = AsyncMock(return_value=[0.1] * 1536)

        @tool
        def dummy(x: str) -> str:
            return x

        agent = Agent(toolkit=toolkit, tools=[dummy])
        agent.state = AgentState(
            session_id="test_session",
            goal="Test goal",
            context_window=["item1", "item2"],
        )
        agent._init_pool()

        return agent

    def test_save_creates_session_dir(self, agent, tmp_path):
        agent._save_session()
        session_dir = tmp_path / ".agent_sessions" / "test_session"
        assert session_dir.exists()
        assert (session_dir / "state.json").exists()

    def test_save_writes_state_json(self, agent, tmp_path):
        agent._save_session()
        state_path = tmp_path / ".agent_sessions" / "test_session" / "state.json"
        restored = AgentState.model_validate_json(state_path.read_text())
        assert restored.session_id == "test_session"
        assert restored.goal == "Test goal"
        assert restored.context_window == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_resume_loads_state(self, agent, tmp_path):
        agent._save_session()

        @tool
        def dummy(x: str) -> str:
            return x

        resumed = await Agent.resume(
            session_id="test_session",
            toolkit=agent.toolkit,
            tools=[dummy],
        )

        assert resumed.state.session_id == "test_session"
        assert resumed.state.goal == "Test goal"
        assert resumed.state.context_window == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_resume_nonexistent_session_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            await Agent.resume(
                session_id="nonexistent",
                toolkit=agent.toolkit,
                tools=[],
            )

    def test_list_sessions(self, agent, tmp_path):
        agent._save_session()

        sessions = Agent.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test_session"
        assert sessions[0]["goal"] == "Test goal"
        assert sessions[0]["status"] == "running"

    def test_list_sessions_empty_when_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sessions = Agent.list_sessions()
        assert sessions == []
