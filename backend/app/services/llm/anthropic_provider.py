"""Native Anthropic Messages API provider (httpx, no SDK dependency)."""

import json
from collections.abc import AsyncIterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.services.llm.base import ChatMessage, ChatProvider, ChatResult

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


def _split_system(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
    system_parts = [m.content for m in messages if m.role == "system"]
    chat = [
        {"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")
    ]
    return "\n\n".join(system_parts), chat


class AnthropicProvider(ChatProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 180.0, max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.default_max_tokens = max_tokens

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=20),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        system, chat = _split_system(messages)
        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature,
            "messages": chat,
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(API_URL, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        return ChatResult(
            text=text,
            model=data.get("model", self.model),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            raw=data,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        system, chat = _split_system(messages)
        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature,
            "messages": chat,
            "stream": True,
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", API_URL, headers=self._headers(), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
