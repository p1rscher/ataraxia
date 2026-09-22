#!/usr/bin/env python3
# tools/test_ai_backend.py
"""
Connection test for the local AI backend.

Run from the bot directory on the dedicated server:

    python tools/test_ai_backend.py

Checks in sequence:
  1. Are the required .env variables set?
  2. Is the gateway reachable?    (/health)
  3. Is the token valid?           (/status)
  4. Is the model installed?      (/api/tags)
  5. Does the model respond?       (/api/chat) - including timing
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import aiohttp
    from dotenv import load_dotenv
except ImportError as exc:
    print(f"Missing dependency: {exc}")
    print("Please run:  pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()

OK = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[ERROR]\033[0m"
WARN = "\033[93m[NOTICE]\033[0m"


async def main() -> int:
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    api_key = (os.getenv("OLLAMA_API_KEY") or "").strip()
    model = (os.getenv("OLLAMA_MODEL") or "").strip()

    print("=" * 66)
    print("  Local AI backend test")
    print("=" * 66)

    # --- 1) Configuration --------------------------------------------------
    if not base_url:
        print(f"{FAIL} OLLAMA_BASE_URL is not set (.env).")
        return 1
    if not model:
        print(f"{FAIL} OLLAMA_MODEL is not set (.env).")
        return 1
    if not api_key:
        print(f"{WARN} OLLAMA_API_KEY is empty - the gateway will be unprotected.")

    print(f"  Backend : {base_url}")
    print(f"  Model   : {model}")
    print(f"  Token   : {'set' if api_key else 'not set'}")
    print("-" * 66)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout = aiohttp.ClientTimeout(total=300, connect=15)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # --- 2) Reachability -----------------------------------------------
        try:
            async with session.get(f"{base_url}/health") as resp:
                if resp.status == 200:
                    print(f"{OK} Gateway reachable (/health)")
                else:
                    print(f"{WARN} /health returned HTTP {resp.status} "
                          f"(possibly direct Ollama access without a gateway)")
        except Exception as exc:
            print(f"{FAIL} Gateway unreachable: {exc}")
            print("        - Is gateway.py running on the Windows machine?")
            print("        - Are the IP and port in OLLAMA_BASE_URL correct?")
            print("        - Are the firewall, port forwarding, and Tailscale active?")
            return 1

        # --- 3) Token -------------------------------------------------------
        try:
            async with session.get(f"{base_url}/status", headers=headers) as resp:
                if resp.status == 401:
                    print(f"{FAIL} Token rejected (HTTP 401).")
                    print("        OLLAMA_API_KEY must exactly match GATEWAY_TOKEN.")
                    return 1
                if resp.status == 403:
                    print(f"{FAIL} IP blocked (HTTP 403) - see ALLOWED_IPS in the gateway.")
                    return 1
                if resp.status == 200:
                    data = await resp.json()
                    print(f"{OK} Token akzeptiert")
                    print(f"     Ollama reachable  : {data.get('ollama_reachable')}")
                    print(f"     Uptime            : {data.get('uptime_seconds')}s")
                    print(f"     Total requests    : {data.get('requests_total')}")
                else:
                    print(f"{WARN} /status lieferte HTTP {resp.status}")
        except Exception as exc:
            print(f"{WARN} /status unavailable: {exc}")

        # --- 4) Model availability -----------------------------------------
        try:
            async with session.get(f"{base_url}/api/tags", headers=headers) as resp:
                if resp.status != 200:
                    print(f"{FAIL} /api/tags returned HTTP {resp.status}")
                    return 1
                data = await resp.json()
                names = [m.get("name", "") for m in data.get("models", [])]
                print(f"{OK} Installed models: {', '.join(names) or '(none)'}")
                if model not in names:
                    stems = {m.split(':')[0] for m in names}
                    if model.split(':')[0] in stems:
                        match = next(m for m in names if m.split(':')[0] == model.split(':')[0])
                        print(f"{WARN} OLLAMA_MODEL='{model}' differs. Please set it to: '{match}'")
                    else:
                        print(f"{FAIL} '{model}' is not installed.")
                        print(f"        On the Windows machine:  ollama pull {model}")
                        return 1
        except Exception as exc:
            print(f"{FAIL} Could not retrieve the model list: {exc}")
            return 1

        # --- 5) Actual generation ------------------------------------------
        print("-" * 66)
        print("  Sending test request... (the first call may take a while,")
        print("  because the model must first be loaded into memory)")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Answer in exactly one short sentence."},
                {"role": "user", "content": "Say hello to the Discord bot."},
            ],
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.7, "num_predict": 60, "num_ctx": 8192},
        }

        started = time.perf_counter()
        try:
            async with session.post(f"{base_url}/api/chat", json=payload, headers=headers) as resp:
                body = await resp.text()
                if resp.status != 200:
                    print(f"{FAIL} HTTP {resp.status}: {body[:300]}")
                    return 1
                import json as _json
                data = _json.loads(body)
        except asyncio.TimeoutError:
            print(f"{FAIL} Timeout. The model is taking too long.")
            print("        Increase REQUEST_TIMEOUT in the gateway and OLLAMA_TIMEOUT_SECONDS,")
            print("        or use a smaller/faster model.")
            return 1
        except Exception as exc:
            print(f"{FAIL} Request failed: {exc}")
            return 1

        elapsed = time.perf_counter() - started
        answer = (data.get("message") or {}).get("content", "").strip()
        prompt_tokens = data.get("prompt_eval_count", 0)
        eval_tokens = data.get("eval_count", 0)
        tps = eval_tokens / elapsed if elapsed > 0 else 0

        print("-" * 66)
        print(f"{OK} Response received in {elapsed:.1f}s")
        print(f"     Tokens  : {prompt_tokens} prompt / {eval_tokens} generated")
        print(f"     Speed   : {tps:.1f} tokens/s")
        print(f"     Content : {answer[:300]}")
        print("=" * 66)

        if elapsed > 30:
            print(f"{WARN} Response time exceeds 30s. Too slow for the chat personality.")
            print("        Options: use KEEP_ALIVE=-1, enable the GPU,")
            print("        or reduce CHATPERSONA_AI_MAX_TOKENS.")
        print("\nEverything is ready. The bot can be started.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
