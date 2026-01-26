"""
Base Agent Module
Provides the foundation for all specialized agents in the AI Review System.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from enum import Enum
import asyncio
import logging

from pydantic import BaseModel, Field


class TaskPriority(str, Enum):
    """Priority levels for agent tasks"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    """Status of agent tasks"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class AgentMessage(BaseModel):
    """Standard message format for agent communication"""
    agent_id: str
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    priority: TaskPriority = TaskPriority.MEDIUM
    inputs: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    parent_task: Optional[str] = None


class AgentResponse(BaseModel):
    """Standard response format from agents"""
    agent_id: str
    task_id: str
    status: TaskStatus
    outputs: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the AI Review System.

    Each agent must implement the process() method which contains
    the core logic for handling tasks.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = agent_id or f"{self.__class__.__name__.lower()}_{uuid4().hex[:8]}"
        self.config = config or {}
        self.logger = logging.getLogger(f"agent.{self.agent_id}")
        self._is_running = False
        self._current_task: Optional[str] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the agent"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the agent's responsibilities"""
        pass

    @property
    def capabilities(self) -> List[str]:
        """List of capabilities this agent provides"""
        return []

    @abstractmethod
    async def process(self, message: AgentMessage) -> AgentResponse:
        """
        Process an incoming message and return a response.

        Args:
            message: The incoming task message to process

        Returns:
            AgentResponse with the results of processing
        """
        pass

    async def execute(self, message: AgentMessage) -> AgentResponse:
        """
        Execute a task with timing and error handling.

        This wrapper method handles common concerns like:
        - Timing execution
        - Error handling
        - Logging
        - Status management
        """
        start_time = datetime.utcnow()
        self._is_running = True
        self._current_task = message.task_id

        self.logger.info(
            f"Starting task {message.task_id} with priority {message.priority}"
        )

        try:
            response = await self.process(message)
            response.execution_time_ms = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000

            self.logger.info(
                f"Task {message.task_id} completed with status {response.status} "
                f"in {response.execution_time_ms:.2f}ms"
            )

            return response

        except Exception as e:
            execution_time = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000

            self.logger.error(
                f"Task {message.task_id} failed: {str(e)}"
            )

            return AgentResponse(
                agent_id=self.agent_id,
                task_id=message.task_id,
                status=TaskStatus.FAILED,
                outputs={},
                execution_time_ms=execution_time,
                errors=[str(e)]
            )

        finally:
            self._is_running = False
            self._current_task = None

    async def validate_inputs(
        self,
        inputs: Dict[str, Any],
        required_fields: List[str]
    ) -> List[str]:
        """
        Validate that required fields are present in inputs.

        Returns:
            List of missing field names (empty if all present)
        """
        missing = [field for field in required_fields if field not in inputs]
        return missing

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "is_running": self._is_running,
            "current_task": self._current_task,
            "capabilities": self.capabilities
        }

    async def health_check(self) -> bool:
        """Check if the agent is healthy and ready to process tasks"""
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.agent_id})>"


class AgentRegistry:
    """
    Registry for managing and discovering agents.
    """

    _instance: Optional["AgentRegistry"] = None

    def __new__(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, BaseAgent] = {}
        return cls._instance

    def register(self, agent: BaseAgent) -> None:
        """Register an agent in the registry"""
        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry"""
        if agent_id in self._agents:
            del self._agents[agent_id]

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID"""
        return self._agents.get(agent_id)

    def get_by_type(self, agent_type: type) -> List[BaseAgent]:
        """Get all agents of a specific type"""
        return [
            agent for agent in self._agents.values()
            if isinstance(agent, agent_type)
        ]

    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered agents"""
        return [agent.get_status() for agent in self._agents.values()]

    async def health_check_all(self) -> Dict[str, bool]:
        """Run health checks on all agents"""
        results = {}
        for agent_id, agent in self._agents.items():
            results[agent_id] = await agent.health_check()
        return results


# Global registry instance
agent_registry = AgentRegistry()
