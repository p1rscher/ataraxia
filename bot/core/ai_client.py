"""OpenAI-compatible multi-provider AI client for Ataraxia.

Groq is tried first by default; Gemini is used automatically if the primary
provider is unavailable, rejects the key/model, or returns a rate-limit error.
The client uses aiohttp (already installed through discord.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

import aiohttp

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(r"^\s*(assistant|ai|bot|answer|reply|response)\s*[:\-]\s*", re.IGNORECASE)
_SURROUNDING_QUOTES_RE = re.compile(r"^\s*[\"'\u201c\u201e\u00ab](.*)[\"'\u201d\u201c\u00bb]\s*$", re.DOTALL)


class AIClientError(RuntimeError):
    """Error communicating with every configured AI provider."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Message:
    role: str = "assistant"
    content: str = ""


@dataclass
class Choice:
    message: Message
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class ChatCompletion:
    id: str
    model: str
    choices: list[Choice]
    usage: Usage
    created: int
    latency_ms: int = 0
    raw: dict = field(default_factory=dict, repr=False)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or "").strip() or default


def sanitize_model_output(text: str) -> str:
    if not text:
        return ""
    return _LEADING_LABEL_RE.sub("", _THINK_BLOCK_RE.sub("", text)).strip()


def strip_surrounding_quotes(text: str) -> str:
    if not text:
        return ""
    match = _SURROUNDING_QUOTES_RE.match(text.strip())
    return match.group(1).strip() if match and match.group(1).strip() else text.strip()


class _StreamFilter:
    """Strip reasoning blocks and leading role labels across SSE chunks."""
    def __init__(self) -> None:
        self.pending = ""
        self.in_think = False
        self.label_buf = ""
        self.label_checked = False

    def _strip_think(self, piece: str) -> str:
        self.pending += piece
        output = []
        while self.pending:
            if self.in_think:
                end = self.pending.find("</think>")
                if end < 0:
                    if len(self.pending) > 4000:
                        self.pending = ""
                    break
                self.pending = self.pending[end + 8:]
                self.in_think = False
                continue
            start = self.pending.find("<think>")
            if start >= 0:
                output.append(self.pending[:start])
                self.pending = self.pending[start + 7:]
                self.in_think = True
                continue
            hold = 0
            for n in range(min(len(self.pending), 6), 0, -1):
                if "<think>".startswith(self.pending[-n:]):
                    hold = n
                    break
            safe = len(self.pending) - hold
            output.append(self.pending[:safe])
            self.pending = self.pending[safe:]
            break
        return "".join(output)

    def feed(self, piece: str) -> str:
        cleaned = self._strip_think(piece)
        if self.label_checked:
            return cleaned
        self.label_buf += cleaned
        if len(self.label_buf) < 24:
            return ""
        self.label_checked = True
        return _LEADING_LABEL_RE.sub("", self.label_buf, count=1)

    def flush(self) -> str:
        tail = "" if self.in_think else self.pending
        self.pending = ""
        if not self.label_checked:
            self.label_checked = True
            return _LEADING_LABEL_RE.sub("", self.label_buf + tail, count=1)
        return tail


# Provider IDs and default model names are kept here so the .env can override
# them without changing bot code. Gemini's OpenAI-compatible REST API is used.
_PROVIDER_DEFAULTS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash-lite", "GEMINI_API_KEY"),
}


class _Completions:
    def __init__(self, client: "AsyncAIClient") -> None:
        self.client = client

    async def create(self, *, messages: Sequence[dict], model: Optional[str] = None,
                     temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                     top_p: Optional[float] = None, stop: Optional[Iterable[str]] = None,
                     stream: bool = False, **_ignored: Any) -> ChatCompletion:
        return await self.client._completion(messages, model, temperature, max_tokens, top_p, stop)


class _Chat:
    def __init__(self, client: "AsyncAIClient") -> None:
        self.completions = _Completions(client)


class AsyncAIClient:
    """Small async client exposing the chat.completions shape used by the cogs."""
    def __init__(self) -> None:
        self.primary = _env("AI_PROVIDER", "groq").lower()
        self.fallback = _env("AI_FALLBACK_PROVIDER", "gemini").lower()
        self.timeout = float(_env("AI_TIMEOUT_SECONDS", "45"))
        self.max_concurrency = max(1, int(_env("AI_MAX_CONCURRENCY", "8")))
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self.chat = _Chat(self)
        self.providers = self._configured_providers()
        self.model = self.providers[0]["model"] if self.providers else _env("AI_MODEL", "openai/gpt-oss-20b")
        logger.info("AI providers ready: %s", " -> ".join(p["name"] for p in self.providers) or "none")

    def _configured_providers(self) -> list[dict[str, str]]:
        configured = []
        for name in dict.fromkeys((self.primary, self.fallback)):
            if name not in _PROVIDER_DEFAULTS:
                logger.warning("Unknown AI provider %r; supported providers: %s", name, ", ".join(_PROVIDER_DEFAULTS))
                continue
            base_url, default_model, key_name = _PROVIDER_DEFAULTS[name]
            key = _env(key_name)
            if not key:
                continue
            provider_model = _env(f"{name.upper()}_MODEL", default_model)
            if name == self.primary:
                provider_model = _env("AI_MODEL", provider_model)
            configured.append({"name": name, "url": _env(f"{name.upper()}_BASE_URL", base_url).rstrip("/"),
                               "model": provider_model, "key": key})
        if not configured:
            logger.warning("No AI provider configured. Add GROQ_API_KEY and/or GEMINI_API_KEY to .env.")
        elif configured[0]["name"] != self.primary:
            logger.warning("Primary provider %s is not configured; using %s", self.primary, configured[0]["name"])
        return configured

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    @staticmethod
    def _payload(provider: dict[str, str], messages: Sequence[dict], model: Optional[str],
                 temperature: Optional[float], max_tokens: Optional[int], top_p: Optional[float],
                 stop: Optional[Iterable[str]], stream: bool = False) -> dict:
        # Provider-specific fallback uses that provider's model, unless the caller
        # explicitly selected a model other than the configured primary default.
        requested = model
        if requested and requested != _env("AI_MODEL", _PROVIDER_DEFAULTS.get(_env("AI_PROVIDER", "groq").lower(), ("", "", ""))[1]):
            chosen_model = requested
        else:
            chosen_model = provider["model"]
        payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": [{"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
                         for m in messages if m and m.get("content") is not None],
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        if top_p is not None:
            payload["top_p"] = float(top_p)
        if stop:
            payload["stop"] = [stop] if isinstance(stop, str) else list(stop)
        return payload

    @staticmethod
    def _headers(provider: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {provider['key']}", "Content-Type": "application/json"}

    async def _completion(self, messages: Sequence[dict], model: Optional[str], temperature: Optional[float],
                          max_tokens: Optional[int], top_p: Optional[float], stop: Optional[Iterable[str]]) -> ChatCompletion:
        if not self.providers:
            raise AIClientError("AI is not configured. Add a provider API key to the bot .env file.")
        errors = []
        session = await self._get_session()
        for provider in self.providers:
            payload = self._payload(provider, messages, model, temperature, max_tokens, top_p, stop)
            started = time.perf_counter()
            try:
                async with self._semaphore, session.post(provider["url"] + "/chat/completions", json=payload,
                                                          headers=self._headers(provider)) as response:
                    body = await response.text()
                    if response.status >= 400:
                        errors.append(f"{provider['name']} HTTP {response.status}: {body[:240]}")
                        logger.warning("AI provider %s returned HTTP %d; trying fallback", provider["name"], response.status)
                        continue
                    data = json.loads(body)
                first = (data.get("choices") or [{}])[0]
                content = sanitize_model_output(((first.get("message") or {}).get("content")) or "")
                if not content:
                    errors.append(f"{provider['name']} returned an empty response")
                    continue
                usage_raw = data.get("usage") or {}
                usage = Usage(int(usage_raw.get("prompt_tokens") or 0), int(usage_raw.get("completion_tokens") or 0),
                              int(usage_raw.get("total_tokens") or 0))
                if not usage.total_tokens:
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                return ChatCompletion(str(data.get("id") or uuid.uuid4().hex), str(data.get("model") or payload["model"]),
                                      [Choice(Message(content=content), finish_reason=first.get("finish_reason") or "stop")],
                                      usage, int(data.get("created") or time.time()),
                                      int((time.perf_counter() - started) * 1000), data)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
                errors.append(f"{provider['name']} {type(exc).__name__}: {exc}")
                logger.warning("AI provider %s failed (%s); trying fallback", provider["name"], exc)
        raise AIClientError("All AI providers failed: " + "; ".join(errors))

    async def stream_chat(self, *, messages: Sequence[dict], model: Optional[str] = None,
                          temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                          top_p: Optional[float] = None, stop: Optional[Iterable[str]] = None,
                          usage_sink: Optional[dict] = None):
        if not self.providers:
            raise AIClientError("AI is not configured. Add a provider API key to the bot .env file.")
        session = await self._get_session()
        errors = []
        for provider in self.providers:
            payload = self._payload(provider, messages, model, temperature, max_tokens, top_p, stop, stream=True)
            filt = _StreamFilter()
            yielded = False
            try:
                async with self._semaphore, session.post(provider["url"] + "/chat/completions", json=payload,
                                                          headers=self._headers(provider)) as response:
                    if response.status >= 400:
                        body = await response.text()
                        errors.append(f"{provider['name']} HTTP {response.status}: {body[:240]}")
                        logger.warning("AI streaming provider %s returned HTTP %d; trying fallback", provider["name"], response.status)
                        continue
                    async for raw_line in response.content:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line.startswith("data:"):
                            continue
                        line = line[5:].strip()
                        if line == "[DONE]":
                            break
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        choices = item.get("choices") or [{}]
                        piece = ((choices[0].get("delta") or {}).get("content")) or ""
                        if piece:
                            visible = filt.feed(piece)
                            if visible:
                                yielded = True
                                yield visible
                        usage = item.get("usage")
                        if usage and usage_sink is not None:
                            prompt = int(usage.get("prompt_tokens") or 0)
                            completion = int(usage.get("completion_tokens") or 0)
                            usage_sink.update(prompt_tokens=prompt, completion_tokens=completion,
                                              total_tokens=int(usage.get("total_tokens") or prompt + completion))
                tail = filt.flush()
                if tail:
                    yielded = True
                    yield tail
                if yielded:
                    return
                errors.append(f"{provider['name']} returned an empty response")
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
                errors.append(f"{provider['name']} {type(exc).__name__}: {exc}")
                if yielded:
                    raise AIClientError(f"{provider['name']} stream failed after partial output: {exc}") from exc
                logger.warning("AI streaming provider %s failed (%s); trying fallback", provider["name"], exc)
        raise AIClientError("All AI providers failed: " + "; ".join(errors))

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None


_shared_client: Optional[AsyncAIClient] = None


def get_ai_client() -> AsyncAIClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = AsyncAIClient()
    return _shared_client


def is_configured() -> bool:
    return bool(_env("GROQ_API_KEY") or _env("GEMINI_API_KEY"))


async def close_ai_client() -> None:
    global _shared_client
    if _shared_client is not None:
        await _shared_client.close()
        _shared_client = None
