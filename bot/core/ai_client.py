# core/ai_client.py
"""
Ollama backend for the Ataraxia bot.

Drop-in replacement for ``groq.AsyncGroq``. The calling syntax remains
identical, so existing cogs only need to be updated when importing and
creating the client:

    from core.ai_client import get_ai_client

    client = get_ai_client()
    completion = await client.chat.completions.create(
        model="pparikh2/phi3.5Q4_K_M",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7,
        max_tokens=200,
        stream=False,
    )
    text = completion.choices[0].message.content
    tokens = completion.usage.total_tokens

HTTP communication runs through aiohttp (already included with discord.py,
so no additional dependency is required).

The native Ollama chat API is used::

    POST {OLLAMA_BASE_URL}/api/chat
    {"model": ..., "messages": [...], "stream": false,
     "keep_alive": "30m", "options": {"temperature": ..., "num_predict": ...}}

If OLLAMA_BASE_URL ends with ``/v1``, the OpenAI-compatible route
``/v1/chat/completions`` is used automatically.

Configuration (all via .env on the dedicated server):

    OLLAMA_BASE_URL          e.g. http://100.x.y.z:8080  (required)
    OLLAMA_API_KEY           gateway bearer token         (recommended)
    OLLAMA_MODEL             default model                (required)
    OLLAMA_TIMEOUT_SECONDS   total timeout, default 120
    OLLAMA_CONNECT_TIMEOUT   connection timeout, default 10
    OLLAMA_MAX_RETRIES       retries, default 2
    OLLAMA_MAX_CONCURRENCY   parallel requests, default 1
    OLLAMA_KEEP_ALIVE        keep model in RAM, default 30m
    OLLAMA_NUM_CTX           context window, default 8192
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

# Some models write internal thoughts in <think> blocks. Phi-3.5 normally does
# not, but other models do, so remove them generically.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(
    r"^\s*(assistant|ai|bot|answer|reply|response)\s*[:\-]\s*", re.IGNORECASE
)
_SURROUNDING_QUOTES_RE = re.compile(r'^\s*["\'\u201c\u201e\u00ab](.*)["\'\u201d\u201c\u00bb]\s*$', re.DOTALL)

# HTTP statuses for which retrying makes sense.
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class AIClientError(RuntimeError):
    """Error communicating with the Ollama backend."""


# --------------------------------------------------------------------------- #
# Response objects (API-compatible with groq / openai)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env_str(name, str(default)))
    except (TypeError, ValueError):
        logger.warning("ai_client: %s is not a valid number; using %s", name, default)
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(_env_str(name, str(default))))
    except (TypeError, ValueError):
        logger.warning("ai_client: %s is not a valid number; using %s", name, default)
        return default


def sanitize_model_output(text: str) -> str:
    """Remove reasoning blocks and role prefixes from the model response."""
    if not text:
        return ""
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _LEADING_LABEL_RE.sub("", cleaned)
    return cleaned.strip()


def strip_surrounding_quotes(text: str) -> str:
    """Small models often wrap their response in quotation marks."""
    if not text:
        return ""
    match = _SURROUNDING_QUOTES_RE.match(text.strip())
    if match:
        inner = match.group(1).strip()
        if inner:
            return inner
    return text.strip()


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class _Completions:
    def __init__(self, client: "AsyncOllama") -> None:
        self._client = client

    async def create(
        self,
        *,
        messages: Sequence[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[Iterable[str]] = None,
        stream: bool = False,
        **_ignored: Any,
    ) -> ChatCompletion:
        if stream:
            # The bot only processes the completed response anyway.
            logger.debug("ai_client: stream=True is ignored (always stream=False).")
        return await self._client._chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop=stop,
        )


class _Chat:
    def __init__(self, client: "AsyncOllama") -> None:
        self.completions = _Completions(client)


class AsyncOllama:
    """Asynchronous client for an Ollama instance (direct or via gateway)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        keep_alive: Optional[str] = None,
        num_ctx: Optional[int] = None,
    ) -> None:
        raw_base = (base_url or _env_str("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.base_url = raw_base
        self.api_key = api_key if api_key is not None else _env_str("OLLAMA_API_KEY", "")
        self.model = model or _env_str("OLLAMA_MODEL", "pparikh2/phi3.5Q4_K_M")
        self.timeout = timeout if timeout is not None else _env_float("OLLAMA_TIMEOUT_SECONDS", 120.0)
        self.connect_timeout = (
            connect_timeout if connect_timeout is not None else _env_float("OLLAMA_CONNECT_TIMEOUT", 10.0)
        )
        self.max_retries = max_retries if max_retries is not None else _env_int("OLLAMA_MAX_RETRIES", 2)
        self.keep_alive = keep_alive or _env_str("OLLAMA_KEEP_ALIVE", "30m")
        self.num_ctx = num_ctx if num_ctx is not None else _env_int("OLLAMA_NUM_CTX", 8192)

        concurrency = max_concurrency if max_concurrency is not None else _env_int("OLLAMA_MAX_CONCURRENCY", 1)
        self.max_concurrency = max(1, concurrency)

        # Determine the endpoint: native Ollama API or OpenAI-compatible route.
        if self.base_url.endswith("/v1"):
            self._style = "openai"
            self._endpoint = f"{self.base_url}/chat/completions"
        else:
            self._style = "native"
            self._endpoint = f"{self.base_url}/api/chat"

        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        self.chat = _Chat(self)

        logger.info(
            "ai_client: Ollama backend %s (style=%s, model=%s, timeout=%.1fs, concurrency=%d, auth=%s)",
            self.base_url, self._style, self.model, self.timeout,
            self.max_concurrency, "yes" if self.api_key else "no",
        )

    # -- internal helpers -------------------------------------------------- #

    @property
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._session_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(
                    total=self.timeout,
                    connect=self.connect_timeout,
                    sock_connect=self.connect_timeout,
                )
                self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _build_payload(
        self,
        *,
        messages: Sequence[dict],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
        top_p: Optional[float],
        stop: Optional[Iterable[str]],
    ) -> dict:
        normalized = [
            {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
            for m in messages
            if m and m.get("content") is not None
        ]

        if self._style == "openai":
            payload: dict[str, Any] = {
                "model": model,
                "messages": normalized,
                "stream": False,
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

        options: dict[str, Any] = {"num_ctx": int(self.num_ctx)}
        if temperature is not None:
            options["temperature"] = float(temperature)
        if max_tokens:
            # OpenAI "max_tokens" is called "num_predict" by Ollama.
            options["num_predict"] = int(max_tokens)
        if top_p is not None:
            options["top_p"] = float(top_p)
        if stop:
            options["stop"] = [stop] if isinstance(stop, str) else list(stop)

        return {
            "model": model,
            "messages": normalized,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": options,
        }

    def _parse_response(self, data: dict, model: str, latency_ms: int) -> ChatCompletion:
        if "choices" in data:  # OpenAI format
            first = (data.get("choices") or [{}])[0]
            content = ((first.get("message") or {}).get("content")) or ""
            finish_reason = first.get("finish_reason") or "stop"
            usage_raw = data.get("usage") or {}
            usage = Usage(
                prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
                completion_tokens=int(usage_raw.get("completion_tokens") or 0),
                total_tokens=int(usage_raw.get("total_tokens") or 0),
            )
        else:  # Native Ollama format
            content = ((data.get("message") or {}).get("content")) or data.get("response") or ""
            finish_reason = data.get("done_reason") or "stop"
            prompt_tokens = int(data.get("prompt_eval_count") or 0)
            completion_tokens = int(data.get("eval_count") or 0)
            usage = Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

        if not usage.total_tokens:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        content = sanitize_model_output(content)
        if not content:
            raise AIClientError("The local model returned an empty response.")

        return ChatCompletion(
            id=f"ollama-{uuid.uuid4().hex[:16]}",
            model=data.get("model") or model,
            choices=[Choice(message=Message(role="assistant", content=content), finish_reason=finish_reason)],
            usage=usage,
            created=int(time.time()),
            latency_ms=latency_ms,
            raw=data,
        )

    # -- public API -------------------------------------------------------- #

    async def _chat_completion(
        self,
        *,
        messages: Sequence[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[Iterable[str]] = None,
    ) -> ChatCompletion:
        target_model = model or self.model
        payload = self._build_payload(
            messages=messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop=stop,
        )

        last_error: Optional[str] = None

        for attempt in range(self.max_retries + 1):
            try:
                session = await self._get_session()
                started = time.perf_counter()

                # Only one request at a time: a local model cannot parallelize
                # meaningfully and would otherwise overload the queue.
                async with self._semaphore:
                    async with session.post(self._endpoint, json=payload, headers=self._headers) as resp:
                        body = await resp.text()

                        if resp.status >= 400:
                            snippet = body[:400].replace("\n", " ")
                            if resp.status in (401, 403):
                                raise AIClientError(
                                    f"Gateway rejected the request (HTTP {resp.status}). "
                                    f"Is OLLAMA_API_KEY correct? Response: {snippet}"
                                )
                            if resp.status == 404:
                                raise AIClientError(
                                    f"Model or endpoint not found (HTTP 404). "
                                    f"Is '{target_model}' installed on the local machine? "
                                    f"Response: {snippet}"
                                )
                            if resp.status in _RETRYABLE_STATUS:
                                last_error = f"HTTP {resp.status}: {snippet}"
                                raise aiohttp.ClientResponseError(
                                    resp.request_info, resp.history,
                                    status=resp.status, message=snippet,
                                )
                            raise AIClientError(f"Ollama HTTP {resp.status}: {snippet}")

                        try:
                            data = json.loads(body)
                        except json.JSONDecodeError as exc:
                            raise AIClientError(
                                f"Invalid JSON response from the backend: {body[:200]}"
                            ) from exc

                latency_ms = int((time.perf_counter() - started) * 1000)
                completion = self._parse_response(data, target_model, latency_ms)
                logger.debug(
                    "ai_client: ok model=%s latency_ms=%d tokens=%d",
                    completion.model, latency_ms, completion.usage.total_tokens,
                )
                return completion

            except AIClientError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                last_error = last_error or f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries:
                    delay = 1.5 * (attempt + 1)
                    logger.warning(
                        "ai_client: attempt %d/%d failed (%s), retrying in %.1fs",
                        attempt + 1, self.max_retries + 1, last_error, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise AIClientError(
                    f"Local AI backend is unreachable ({self.base_url}): {last_error}"
                ) from exc

        raise AIClientError(f"Local AI backend is unreachable ({self.base_url}): {last_error}")

    async def list_models(self) -> list[str]:
        """Return the names of installed models (for health checks)."""
        base = self.base_url[:-3].rstrip("/") if self.base_url.endswith("/v1") else self.base_url
        session = await self._get_session()
        async with session.get(f"{base}/api/tags", headers=self._headers) as resp:
            if resp.status >= 400:
                raise AIClientError(f"/api/tags returned HTTP {resp.status}")
            data = await resp.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    async def warmup(self, model: Optional[str] = None) -> bool:
        """Preload the model into memory. Errors are not fatal."""
        target = model or self.model
        try:
            completion = await self._chat_completion(
                messages=[{"role": "user", "content": "ping"}],
                model=target,
                temperature=0.0,
                max_tokens=1,
            )
            logger.info("ai_client: Warmup ok (model=%s, %dms)", target, completion.latency_ms)
            return True
        except Exception as exc:  # noqa: BLE001 - Warmup must never stop the bot
            logger.warning("ai_client: warmup failed (%s): %s", target, exc)
            return False

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None


# --------------------------------------------------------------------------- #
# Shared instance
# --------------------------------------------------------------------------- #

_shared_client: Optional[AsyncOllama] = None


def get_ai_client() -> AsyncOllama:
    """Return the client shared across the process.

    All cogs share a session and a concurrency limit so the local machine is
    not overwhelmed by multiple cogs at once.
    """
    global _shared_client
    if _shared_client is None:
        _shared_client = AsyncOllama()
    return _shared_client


def is_configured() -> bool:
    """Return True if OLLAMA_BASE_URL is set in .env."""
    return bool(_env_str("OLLAMA_BASE_URL", ""))


async def close_ai_client() -> None:
    global _shared_client
    if _shared_client is not None:
        await _shared_client.close()
        _shared_client = None
