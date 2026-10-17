import os
import re
import time
import asyncio
import logging
from typing import Optional, List, Callable, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_env_fallback():
    """Fallback reader for .env file if python-dotenv is not installed."""
    if os.getenv("GROQ_API_KEYS"):
        return
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("\"'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception as e:
            logger.debug(f"Failed to read .env in fallback: {e}")


_load_env_fallback()


@dataclass
class KeyState:
    api_key: str
    available_at: float = 0.0  # Unix timestamp when key recovers from 429


class GroqKeyManager:
    """
    Manages a pool of Groq API keys with timestamp-based rate limit tracking (429 cooldowns).
    Rotates keys seamlessly across LangGraph nodes or LLM calls.
    """

    def __init__(self, keys: Optional[List[str]] = None, default_cooldown: float = 20.0):
        if keys is None:
            raw_keys = os.getenv("GROQ_API_KEYS", "")
            keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

        if not keys:
            single_key = os.getenv("GROQ_API_KEY", "")
            if single_key:
                keys = [single_key.strip()]

        self.keys = [KeyState(api_key=k) for k in keys]
        self.default_cooldown = default_cooldown
        self._current_index = 0
        self._lock = asyncio.Lock()

        logger.info(f"Initialized GroqKeyManager with {len(self.keys)} API keys.")

    def _parse_retry_after(self, error: Exception) -> float:
        """Extract wait duration in seconds from 429 response headers or error message."""
        # 1. Check response headers if available (e.g. groq.RateLimitError)
        response = getattr(error, "response", None)
        if response is not None:
            headers = getattr(response, "headers", {})
            if "retry-after" in headers:
                try:
                    return float(headers["retry-after"])
                except (ValueError, TypeError):
                    pass

        # 2. Parse from error message (e.g. "try again in 14.5s" or "try again in 2m3s")
        msg = str(error)
        match_s = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
        if match_s:
            return float(match_s.group(1))

        match_m = re.search(r"try again in (\d+)\s*m(?:in)?(?:\s*(\d+)\s*s)?", msg, re.IGNORECASE)
        if match_m:
            mins = float(match_m.group(1))
            secs = float(match_m.group(2) or 0)
            return mins * 60.0 + secs

        match_ms = re.search(r"try again in (\d+(?:\.\d+)?)\s*ms", msg, re.IGNORECASE)
        if match_ms:
            return float(match_ms.group(1)) / 1000.0

        return self.default_cooldown

    async def get_available_key(self) -> str:
        """
        Returns an API key that is currently available.
        If all keys are rate-limited, sleeps until the earliest key unlocks.
        """
        wait_time = 0.0
        earliest_key = None

        async with self._lock:
            now = time.time()
            total_keys = len(self.keys)
            if total_keys == 0:
                raise RuntimeError("No Groq API keys configured in GROQ_API_KEYS or GROQ_API_KEY.")

            # Search for an available key in round-robin order
            for i in range(total_keys):
                idx = (self._current_index + i) % total_keys
                if self.keys[idx].available_at <= now:
                    self._current_index = (idx + 1) % total_keys
                    return self.keys[idx].api_key

            # If all keys are currently cooling down, find the one that recovers earliest
            earliest_key = min(self.keys, key=lambda k: k.available_at)
            wait_time = max(0.0, earliest_key.available_at - now)
            logger.warning(
                f"All {total_keys} Groq keys are rate limited. "
                f"Waiting {wait_time:.2f}s for earliest key to recover."
            )

        # Sleep outside the lock so we don't block other tasks inspecting state
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        return earliest_key.api_key if earliest_key else self.keys[0].api_key

    async def mark_key_rate_limited(self, api_key: str, error: Exception):
        """Marks a key as unavailable until its cooldown timestamp expires."""
        async with self._lock:
            wait_seconds = self._parse_retry_after(error)
            cooldown_until = time.time() + wait_seconds

            for k in self.keys:
                if k.api_key == api_key:
                    k.available_at = cooldown_until
                    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
                    logger.warning(
                        f"Groq key {masked_key} rate limited (429). "
                        f"Cooldown for {wait_seconds:.2f}s (until {cooldown_until:.1f})."
                    )
                    break

    async def execute_with_retry(self, call_fn: Callable[[str], Any], max_retries: Optional[int] = None) -> Any:
        """
        Executes an async function call (call_fn(api_key)).
        Automatically catches 429 rate limit errors, updates timestamp, rotates key, and retries.
        """
        if max_retries is None:
            max_retries = max(len(self.keys) * 2, 4)

        last_error = None
        for attempt in range(max_retries):
            key = await self.get_available_key()
            try:
                # call_fn can be async or sync
                res = call_fn(key)
                if asyncio.iscoroutine(res):
                    return await res
                return res
            except Exception as e:
                err_str = str(e).lower()
                status_code = getattr(e, "status_code", None)

                # Check if it is a 429 Rate Limit error
                if status_code == 429 or "rate_limit" in err_str or "429" in err_str:
                    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                    logger.info(f"Attempt {attempt + 1} with key {masked} hit 429 rate limit. Rotating key...")
                    await self.mark_key_rate_limited(key, e)
                    last_error = e
                    continue
                else:
                    # Non-rate-limit error (e.g. invalid arguments, model not found)
                    raise e

        raise RuntimeError(f"Exceeded max retries ({max_retries}) across Groq keys. Last error: {last_error}")

    def get_status(self) -> List[dict]:
        """Returns diagnostic status of all keys and their cooldown timestamps."""
        now = time.time()
        return [
            {
                "key_preview": k.api_key[:8] + "..." + k.api_key[-4:] if len(k.api_key) > 12 else "***",
                "is_available": k.available_at <= now,
                "cooldown_remaining_sec": max(0.0, round(k.available_at - now, 2)),
            }
            for k in self.keys
        ]


# Global singleton instance
groq_key_manager = GroqKeyManager()
