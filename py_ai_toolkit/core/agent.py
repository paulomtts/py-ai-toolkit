import logging
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from chonkie import TokenChunker
from pydantic import BaseModel, Field

from py_ai_toolkit.core.context_pool import ContextPool
from py_ai_toolkit.core.enums import AgentStatus
from py_ai_toolkit.core.tool import Tool
from py_ai_toolkit.core.toolkit import Toolkit

logger = logging.getLogger("Agent")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class AgentState(BaseModel):
    session_id: str
    goal: str
    context_window: list[str] = []
    status: AgentStatus = AgentStatus.RUNNING
    has_overflow: bool = False


class AgentDecision(BaseModel):
    """Decision model for agent actions."""

    action: Literal["think", "use_tool", "complete"] = Field(
        description="The type of action to take"
    )
    reasoning: str | None = Field(
        default=None, description="Reasoning when action is 'think'"
    )
    tool_name: str | None = Field(
        default=None, description="Tool name when action is 'use_tool'"
    )
    summary: str | None = Field(
        default=None, description="Summary when action is 'complete'"
    )


class ToolCallOutcome(BaseModel):
    tool_name: str
    tool_args: dict[str, Any]
    success: bool
    result: Any | None = None
    error: str | None = None


class CompactionSummary(BaseModel):
    summary: str
    key_findings: list[str]
    references: list[str]


class Agent:
    def __init__(self, toolkit: Toolkit, tools: list[Tool], max_iterations: int = 50):
        self.toolkit = toolkit
        self.tools = {t.name: t for t in tools}
        self.state: AgentState | None = None
        self.max_context_tokens = 80_000
        self.compaction_threshold = 0.6
        self.max_iterations = max_iterations
        self.chunker = TokenChunker(chunk_size=400, chunk_overlap=80)
        self.pool: ContextPool | None = None

    async def run(self, goal: str) -> AgentState:
        self.state = AgentState(
            session_id=uuid4().hex,
            goal=goal,
        )
        logger.debug(
            f"Agent started - session_id: {self.state.session_id}, goal: {goal}"
        )
        self._init_pool()

        try:
            iteration_count = 0
            while self.state.status == AgentStatus.RUNNING:
                iteration_count += 1
                logger.info(f"Loop iteration {iteration_count}")
                if iteration_count > self.max_iterations:
                    logger.warning(f"Max iterations ({self.max_iterations}) exceeded")
                    self.state.status = AgentStatus.ERROR
                    self.state.context_window.append(
                        f"[Error] Max iterations ({self.max_iterations}) exceeded"
                    )
                    break
                await self._loop_iteration()
        finally:
            self._save_session()
            logger.debug(
                f"Agent finished - status: {self.state.status.value}, iterations: {iteration_count}"
            )

        return self.state

    async def _loop_iteration(self):
        if self._needs_compaction():
            logger.debug("Context compaction needed, starting compaction")
            await self._compact_context()

        retrieved = []
        if self.state.has_overflow:
            logger.debug("Retrieving chunks from context pool")
            retrieved = await self._retrieve_chunks()
            logger.debug(f"Retrieved {len(retrieved)} chunks")

        decision = await self._get_decision(retrieved)
        await self._execute_decision(decision)

    async def _execute_decision(self, decision: AgentDecision):
        logger.debug(f"Executing decision: {decision.action}")
        if decision.action == "think":
            logger.debug(
                f"Think decision - reasoning: {decision.reasoning[:100] if decision.reasoning else None}"
            )
            self.state.context_window.append(f"[Think] {decision.reasoning}")

        elif decision.action == "use_tool":
            logger.debug(f"Use tool decision - tool: {decision.tool_name}")
            outcome = await self._execute_tool(decision.tool_name)
            self.state.context_window.append(
                f"[Tool: {decision.tool_name}] {outcome.result or outcome.error}"
            )

        elif decision.action == "complete":
            logger.debug(
                f"Complete decision - summary: {decision.summary[:100] if decision.summary else None}"
            )
            self.state.context_window.append(f"[Complete] {decision.summary}")
            self.state.status = AgentStatus.COMPLETE

    async def _execute_tool(self, tool_name: str) -> ToolCallOutcome:
        tool = self.tools[tool_name]
        logger.debug(f"Executing tool: {tool_name}")

        try:
            logger.debug(f"Populating arguments for tool: {tool_name}")
            args = await self.toolkit.asend(
                response_model=tool.parameters,
                template="""Fill the arguments for the {{ tool_name }} tool.

Tool description: {{ tool_description }}

Current context:
{% for item in context %}
{{ item }}
{% endfor %}
""",
                tool_name=tool_name,
                tool_description=tool.description,
                context=self.state.context_window,
            )
            logger.info(f"Tool {tool_name} args: {args.content.model_dump()}")

            result = await tool.execute(**args.content.model_dump())
            logger.info(f"Tool {tool_name} result: {str(result)[:100]}")

            return ToolCallOutcome(
                tool_name=tool_name,
                tool_args=args.content.model_dump(),
                success=True,
                result=result,
            )
        except Exception as e:
            logger.info(f"Tool {tool_name} result: ERROR - {str(e)}")
            return ToolCallOutcome(
                tool_name=tool_name,
                tool_args={},
                success=False,
                error=str(e),
            )

    async def _get_decision(self, retrieved: list[str]) -> AgentDecision:
        tool_descriptions = [
            f"- {name}: {t.description} ({t.tool_type.value})"
            for name, t in self.tools.items()
        ]
        logger.debug(
            f"Getting decision from LLM - context_len: {len(self.state.context_window)}, retrieved_chunks: {len(retrieved)}"
        )

        tool_calls = [
            item for item in self.state.context_window if item.startswith("[Tool:")
        ]

        template = """You are an agent working toward a goal. You will receive a goal and the current context. You must then choose your next step toward accomplishing the goal - or indicate that you have completed the goal. Rules:

        1. In your first round, you should choose to think about the goal to produce a reasoning of how you could achieve it with the available tools.
        2. Try and validate whether the task has been completed by using the tools at your disposal - if none can help you with that, then default to the current context to try and understand whether the goal has been achieved.

Goal: {{ goal }}

Available tools:
{% for tool in tools %}
{{ tool }}
{% endfor %}

{% if context %}
Actions taken so far:
{% for item in context %}
{{ item }}
{% endfor %}
{% endif %}

{% if retrieved %}
Retrieved from memory:
{% for item in retrieved %}
{{ item }}
{% endfor %}
{% endif %}

Choose your next action:
- use_tool: Use a tool to make progress toward the goal (provide tool_name)
- think: Reason about what to do next (provide reasoning)
- complete: ONLY use this when you have successfully completed ALL parts of the goal AND verified the result (provide summary of what was done)
"""

        decision = (
            await self.toolkit.asend(
                response_model=AgentDecision,
                template=template,
                goal=self.state.goal,
                context=self.state.context_window,
                tool_calls=tool_calls,
                retrieved=retrieved,
                tools=tool_descriptions,
            )
        ).content

        decision_msg = f"LLM decided to: {decision.action}"
        if decision.action == "use_tool":
            decision_msg += f" (tool: {decision.tool_name})"
        elif decision.action == "think":
            decision_msg += (
                f" (reasoning: {decision.reasoning if decision.reasoning else None}...)"
            )
        elif decision.action == "complete":
            decision_msg += (
                f" (summary: {decision.summary if decision.summary else None}...)"
            )
        logger.info(decision_msg)

        return decision

    def _needs_compaction(self) -> bool:
        total_chars = sum(len(item) for item in self.state.context_window)
        estimated_tokens = total_chars // 4
        return estimated_tokens > self.max_context_tokens

    async def _compact_context(self):
        split_idx = int(len(self.state.context_window) * self.compaction_threshold)
        to_compact = self.state.context_window[:split_idx]
        to_keep = self.state.context_window[split_idx:]
        logger.debug(
            f"Compacting context - compacting {len(to_compact)} items, keeping {len(to_keep)} items"
        )

        summary = await self._summarize_content(to_compact)
        logger.debug(f"Generated summary with {len(summary.key_findings)} key findings")
        await self._store_chunks(to_compact)
        logger.debug(f"Stored {len(to_compact)} items as chunks")

        self.state.context_window = [
            f"[Compacted Summary]\n{summary.summary}\n\nKey findings: {summary.key_findings}"
        ] + to_keep

        self.state.has_overflow = True
        logger.debug("Context compaction completed, overflow flag set")

    async def _summarize_content(self, content: list[str]) -> CompactionSummary:
        return (
            await self.toolkit.asend(
                response_model=CompactionSummary,
                template="""Summarize the following context that is being archived.
Preserve key information, decisions, and outcomes.
Note what files/tools/resources were involved.

Content:
{% for item in content %}
{{ item }}
{% endfor %}
""",
                content=content,
            )
        ).content

    async def _store_chunks(self, content: list[str]):
        full_text = "\n\n".join(content)
        chunks = self.chunker.chunk(full_text)

        for chunk in chunks:
            embedding = await self._embed(chunk.text)
            await self.pool.store(
                text=chunk.text,
                embedding=embedding,
                session_id=self.state.session_id,
            )

    async def _retrieve_chunks(self, top_k: int = 5) -> list[str]:
        query = self._build_retrieval_query()
        logger.debug(f"Retrieving chunks - query: {query[:100]}..., top_k: {top_k}")
        query_embedding = await self._embed(query)

        results = await self.pool.hybrid_search(
            query_text=query,
            query_embedding=query_embedding,
            session_id=self.state.session_id,
            top_k=top_k,
        )
        logger.debug(f"Retrieved {len(results)} chunks from context pool")

        return [r.text for r in results]

    def _build_retrieval_query(self) -> str:
        recent = self.state.context_window[-3:] if self.state.context_window else []
        return f"Goal: {self.state.goal}\n\nRecent context:\n" + "\n".join(recent)

    async def _embed(self, text: str) -> list[float]:
        return await self.toolkit.embed(text)

    def _init_pool(self):
        session_dir = Path(f".agent_sessions/{self.state.session_id}")
        session_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Initializing context pool - session_dir: {session_dir}")

        self.pool = ContextPool(
            db_path=str(session_dir / "pool.db"),
            embedding_dim=1536,
        )
        logger.debug("Context pool initialized")

    def _save_session(self):
        session_dir = Path(f".agent_sessions/{self.state.session_id}")
        session_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(
            f"Saving session - session_id: {self.state.session_id}, status: {self.state.status.value}"
        )

        state_path = session_dir / "state.json"
        state_path.write_text(self.state.model_dump_json(indent=2))
        logger.debug(f"Session saved to {state_path}")

    @classmethod
    async def resume(
        cls, session_id: str, toolkit: Toolkit, tools: list[Tool]
    ) -> "Agent":
        logger.debug(f"Resuming session - session_id: {session_id}")
        session_dir = Path(f".agent_sessions/{session_id}")

        if not session_dir.exists():
            logger.error(f"Session {session_id} not found")
            raise ValueError(f"Session {session_id} not found")

        state_path = session_dir / "state.json"
        state = AgentState.model_validate_json(state_path.read_text())
        logger.debug(
            f"Loaded session state - goal: {state.goal}, status: {state.status.value}"
        )

        agent = cls(toolkit=toolkit, tools=tools)
        agent.state = state
        agent._init_pool()
        logger.debug("Session resumed successfully")

        return agent

    @staticmethod
    def list_sessions() -> list[dict[str, Any]]:
        sessions_dir = Path(".agent_sessions")
        if not sessions_dir.exists():
            return []

        sessions = []
        for session_dir in sessions_dir.iterdir():
            if session_dir.is_dir():
                state_path = session_dir / "state.json"
                if state_path.exists():
                    state = AgentState.model_validate_json(state_path.read_text())
                    sessions.append(
                        {
                            "session_id": state.session_id,
                            "goal": state.goal,
                            "status": state.status.value,
                        }
                    )
        return sessions
