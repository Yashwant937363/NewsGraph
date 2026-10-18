import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set
from dotenv import dotenv_values
import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("news_pipeline.groq")


class GroqClient:
    """
    Manages Groq API calls with multi-key rotation, automatic fallback on 429 rate limits,
    LRU key distribution, rate pacing, fallback model switching, and exponential backoff.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        env_path: str = ".env",
        keys: Optional[List[str]] = None,
    ):
        self.settings = settings or get_settings()
        self.env_path = env_path
        self._keys: List[str] = []
        self._current_index: int = 0
        self._exhausted_keys: Set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None
        self._custom_keys: bool = bool(keys)
        self._key_last_used: Dict[str, float] = {}
        self._last_request_time: float = 0.0
        self._active_model: str = self.settings.groq_model
        self._fallback_model: str = getattr(self.settings, "groq_fallback_model", "openai/gpt-oss-20b")
        self._requests_per_minute: int = getattr(self.settings, "groq_requests_per_minute", 8)

        if keys:
            self._keys = [k.strip() for k in keys if k.strip()]
        else:
            self.reload_keys()

    def reload_keys(self) -> None:
        """Reloads Groq API keys from settings and directly from .env file."""
        if getattr(self, "_custom_keys", False):
            return

        keys_set = set()
        ordered_keys = []

        if os.path.exists(self.env_path):
            env_vals = dotenv_values(self.env_path)
            env_keys_str = env_vals.get("GROQ_API_KEYS", "")
            if env_keys_str:
                for k in env_keys_str.split(","):
                    k_clean = k.strip()
                    if k_clean and k_clean not in keys_set:
                        keys_set.add(k_clean)
                        ordered_keys.append(k_clean)

        for k in self.settings.get_groq_api_keys():
            k_clean = k.strip()
            if k_clean and k_clean not in keys_set:
                keys_set.add(k_clean)
                ordered_keys.append(k_clean)

        if ordered_keys:
            self._keys = ordered_keys
            logger.info(f"GroqClient: Loaded {len(self._keys)} Groq API key(s) into rotator pool.")
        else:
            logger.warning("GroqClient: No GROQ_API_KEYS found in settings or .env!")

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    def get_current_key(self) -> str:
        if not self._keys:
            self.reload_keys()
        if not self._keys:
            raise ValueError("No Groq API keys available. Please add GROQ_API_KEYS to .env.")
        return self._keys[self._current_index % len(self._keys)]

    def rotate_key(self, reason: str = "rate limit") -> str:
        old_key = self.get_current_key()
        self._exhausted_keys.add(old_key)
        self.reload_keys()

        start_idx = self._current_index
        for offset in range(1, len(self._keys) + 1):
            next_idx = (start_idx + offset) % len(self._keys)
            candidate = self._keys[next_idx]
            if candidate not in self._exhausted_keys:
                self._current_index = next_idx
                logger.info(
                    f"Rotated Groq API key due to {reason}. Switched to key "
                    f"[{candidate[:8]}...] (index {self._current_index + 1}/{len(self._keys)})."
                )
                return candidate

        # If all keys exhausted, reset exhausted pool and rotate
        self._exhausted_keys.clear()
        self._current_index = (self._current_index + 1) % len(self._keys)
        next_key = self._keys[self._current_index]
        logger.warning(
            f"All Groq API keys reached limit. Cleared exhausted set; rotating to key [{next_key[:8]}...]."
        )
        return next_key

    @property
    def active_model(self) -> str:
        return self._active_model

    @active_model.setter
    def active_model(self, model: str) -> None:
        self._active_model = model

    @property
    def fallback_model(self) -> str:
        return self._fallback_model

    @property
    def requests_per_minute(self) -> int:
        return self._requests_per_minute

    @requests_per_minute.setter
    def requests_per_minute(self, rpm: int) -> None:
        self._requests_per_minute = rpm

    def get_optimal_key(self) -> str:
        """
        Selects the least-recently-used key among non-exhausted keys.
        Distributes requests evenly across all available keys in the pool.
        """
        if not self._keys:
            self.reload_keys()
        if not self._keys:
            raise ValueError("No Groq API keys available. Please add GROQ_API_KEYS to .env.")

        available = [k for k in self._keys if k not in self._exhausted_keys]
        if not available:
            self._exhausted_keys.clear()
            available = self._keys

        best_key = min(available, key=lambda k: self._key_last_used.get(k, 0.0))
        self._current_index = self._keys.index(best_key)
        return best_key

    def mark_key_used(self, key: str) -> None:
        self._key_last_used[key] = time.time()

    async def _pace_request(self) -> None:
        """
        Paces API requests according to requests_per_minute setting.
        For example, 8 req/min enforces at least 7.5s interval between requests,
        preventing any single key or the pool from exceeding TPM limits.
        """
        if self._requests_per_minute <= 0:
            return
        min_interval = 60.0 / float(self._requests_per_minute)
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < min_interval and self._last_request_time > 0:
            wait_sec = min_interval - elapsed
            logger.info(
                f"⏱️ Rate Pacing: waiting {wait_sec:.1f}s to respect {self._requests_per_minute} req/min limit..."
            )
            await asyncio.sleep(wait_sec)
        self._last_request_time = time.time()

    def switch_to_fallback_model(self, reason: str = "TPM limit reached") -> str:
        """Switches active model to fallback model (e.g. openai/gpt-oss-20b)."""
        if self._fallback_model and self._active_model != self._fallback_model:
            old_model = self._active_model
            self._active_model = self._fallback_model
            msg = (
                f"\n{'='*75}\n"
                f"🔀 [GROQ MODEL FALLBACK ACTIVATED]\n"
                f"  • Reason        : {reason}\n"
                f"  • Previous Model: {old_model}\n"
                f"  • Fallback Model: {self._active_model}\n"
                f"  • Action        : Retrying with high-throughput fallback model...\n"
                f"{'='*75}\n"
            )
            print(msg, flush=True)
            logger.warning(msg)
            return self._active_model
        return self._active_model

    async def get_http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=45.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _log_and_print_rate_limit(self, resp: httpx.Response, key: str, status_code: int) -> str:
        """
        Extracts detailed limit information from Groq error body and rate limit headers,
        and outputs a formatted diagnostic message to both logger and stdout.
        Returns the formatted error message string.
        """
        try:
            body = resp.json()
            err_data = body.get("error", {})
            err_msg = err_data.get("message", resp.text)
            err_type = err_data.get("type", "")
            err_code = err_data.get("code", "")
        except Exception:
            err_msg = resp.text
            err_type = ""
            err_code = ""

        # Identify which specific limit is being hit based on error message or headers
        limit_kind = "General Rate Limit"
        msg_lower = err_msg.lower()
        if "tokens per minute" in msg_lower or "(tpm)" in msg_lower or " tpm" in msg_lower:
            limit_kind = "TPM (Tokens Per Minute)"
        elif "requests per minute" in msg_lower or "(rpm)" in msg_lower or " rpm" in msg_lower:
            limit_kind = "RPM (Requests Per Minute)"
        elif "requests per day" in msg_lower or "(rpd)" in msg_lower or " rpd" in msg_lower:
            limit_kind = "RPD (Requests Per Day)"
        elif "tokens per day" in msg_lower or "(tpd)" in msg_lower or " tpd" in msg_lower:
            limit_kind = "TPD (Tokens Per Day)"
        elif status_code == 413 or "too large" in msg_lower:
            limit_kind = "Payload / Context Too Large (exceeds TPM or context limit)"

        # Extract rate limit headers if present
        headers = resp.headers
        limit_tokens = headers.get("x-ratelimit-limit-tokens")
        rem_tokens = headers.get("x-ratelimit-remaining-tokens")
        reset_tokens = headers.get("x-ratelimit-reset-tokens")
        limit_req = headers.get("x-ratelimit-limit-requests")
        rem_req = headers.get("x-ratelimit-remaining-requests")
        reset_req = headers.get("x-ratelimit-reset-requests")
        retry_after = headers.get("retry-after") or headers.get("Retry-After")

        # Build diagnostic output
        key_masked = f"{key[:8]}...{key[-4:]}" if len(key) >= 12 else (f"{key[:6]}..." if len(key) >= 6 else key)
        lines = [
            f"\n{'='*75}",
            f"🚨 [GROQ API HTTP {status_code} RATE LIMIT DETECTED]",
            f"  • Key           : [{key_masked}]",
            f"  • Limit Hit     : {limit_kind}",
            f"  • Groq Error    : {err_msg}",
        ]
        if err_code or err_type:
            lines.append(f"  • Error Details : code='{err_code}', type='{err_type}'")
        if limit_tokens or rem_tokens or reset_tokens:
            lines.append(f"  • Token Limits  : limit={limit_tokens}, remaining={rem_tokens}, reset={reset_tokens}")
        if limit_req or rem_req or reset_req:
            lines.append(f"  • Request Limits: limit={limit_req}, remaining={rem_req}, reset={reset_req}")
        if retry_after:
            lines.append(f"  • Retry After   : {retry_after}s")
        lines.append("  • Next Action   : Rotating API key in pool and applying backoff...")
        lines.append(f"{'='*75}\n")

        formatted_msg = "\n".join(lines)
        print(formatted_msg, flush=True)
        logger.warning(formatted_msg)
        return formatted_msg

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        response_json: bool = True,
        max_retries: int = 5,
    ) -> Dict[str, Any]:
        """
        Sends chat completion request to Groq OpenAI-compatible endpoint.
        Handles LRU key distribution, rate pacing, key rotation on 429,
        fallback model switching on TPM limits, retry with backoff, and JSON parsing.
        """
        await self._pace_request()
        client = await self.get_http_client()
        url = "https://api.groq.com/openai/v1/chat/completions"

        payload: Dict[str, Any] = {
            "model": self._active_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_json:
            payload["response_format"] = {"type": "json_object"}

        retries = 0
        backoff_sec = 2.0

        while retries < max_retries:
            key = self.get_optimal_key()
            self.mark_key_used(key)
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }

            try:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    if response_json:
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            # Try regex match for JSON substring
                            match = re.search(r"\{.*\}", content, re.DOTALL)
                            if match:
                                return json.loads(match.group(0))
                            raise ValueError(f"Failed to parse JSON from model response: {content}")
                    return {"text": content}

                elif resp.status_code in (413, 429):
                    limit_kind = self._log_and_print_rate_limit(resp, key, resp.status_code)
                    if ("TPM" in limit_kind or resp.status_code == 413 or "tpm" in resp.text.lower()) and self._active_model != self._fallback_model:
                        self.switch_to_fallback_model(reason=f"HTTP {resp.status_code} ({limit_kind})")
                        payload["model"] = self._active_model

                    self.rotate_key(reason=f"Status {resp.status_code} Rate Limit")
                    retries += 1
                    retry_hdr = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
                    if retry_hdr:
                        try:
                            wait_t = float(retry_hdr)
                            backoff_sec = max(backoff_sec, min(wait_t + 0.5, 20.0))
                        except (ValueError, TypeError):
                            pass
                    await asyncio.sleep(backoff_sec)
                    backoff_sec = min(backoff_sec * 1.5, 15.0)

                elif resp.status_code in (401, 403):
                    logger.error(f"Groq API unauthorized ({resp.status_code}) on key [{key[:8]}...]. Rotating key...")
                    self.rotate_key(reason=f"Status {resp.status_code}")
                    retries += 1

                else:
                    logger.error(f"Groq API error {resp.status_code}: {resp.text}")
                    retries += 1
                    await asyncio.sleep(backoff_sec)
                    backoff_sec = min(backoff_sec * 1.5, 10.0)

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(f"Groq network/timeout error ({exc}). Retrying...")
                retries += 1
                await asyncio.sleep(backoff_sec)

        raise RuntimeError(f"Groq API call failed after {max_retries} attempts.")

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        max_retries: int = 5,
    ) -> Dict[str, Any]:
        """
        Sends chat completion request with OpenAI-compatible tools/functions.
        Returns the assistant message dict containing potential 'tool_calls'.
        Handles LRU key distribution, rate pacing, key rotation on 429/401,
        fallback model switching on TPM limits, and exponential backoff.
        Default max_tokens is capped at 512 to preserve TPM budget.
        """
        await self._pace_request()
        client = await self.get_http_client()
        url = "https://api.groq.com/openai/v1/chat/completions"

        payload: Dict[str, Any] = {
            "model": self._active_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
        }

        retries = 0
        backoff_sec = 2.0

        while retries < max_retries:
            key = self.get_optimal_key()
            self.mark_key_used(key)
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }

            try:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    message = choice.get("message", {})
                    return message

                elif resp.status_code in (413, 429):
                    limit_kind = self._log_and_print_rate_limit(resp, key, resp.status_code)
                    if ("TPM" in limit_kind or resp.status_code == 413 or "tpm" in resp.text.lower()) and self._active_model != self._fallback_model:
                        self.switch_to_fallback_model(reason=f"HTTP {resp.status_code} ({limit_kind})")
                        payload["model"] = self._active_model

                    self.rotate_key(reason=f"Status {resp.status_code} Limit")
                    retries += 1
                    retry_hdr = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
                    if retry_hdr:
                        try:
                            wait_t = float(retry_hdr)
                            backoff_sec = max(backoff_sec, min(wait_t + 0.5, 20.0))
                        except (ValueError, TypeError):
                            pass
                    await asyncio.sleep(backoff_sec)
                    backoff_sec = min(backoff_sec * 2.0, 20.0)

                elif resp.status_code in (401, 403):
                    logger.error(f"Groq API unauthorized ({resp.status_code}) on key [{key[:8]}...]. Rotating key...")
                    self.rotate_key(reason=f"Status {resp.status_code}")
                    retries += 1

                else:
                    logger.error(f"Groq API error {resp.status_code}: {resp.text}")
                    retries += 1
                    await asyncio.sleep(backoff_sec)
                    backoff_sec = min(backoff_sec * 1.5, 12.0)

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(f"Groq network/timeout error ({exc}). Retrying...")
                retries += 1
                await asyncio.sleep(backoff_sec)

        raise RuntimeError(f"Groq API tools call failed after {max_retries} attempts.")


