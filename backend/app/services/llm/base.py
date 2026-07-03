"""Provider-agnostic chat/embedding interfaces."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict = field(default_factory=dict)


class ChatProvider(ABC):
    """A chat-completion backend."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult: ...

    @abstractmethod
    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield text deltas."""
        ...


class EmbeddingProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
