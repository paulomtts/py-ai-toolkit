from enum import Enum


class ToolType(str, Enum):
    GATHER = "gather"
    ACTION = "action"


class AgentStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"
