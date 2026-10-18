import logging
import os
from typing import List, Optional, Set
from dotenv import dotenv_values
from app.config import get_settings

logger = logging.getLogger("news_pipeline.key_rotator")


class KeyRotator:
    """
    Manages multiple NewsAPI keys, with rotation on rate limits (429)
    or quota exhaustion, and supports reloading keys dynamically from .env.
    """

    def __init__(self, keys: Optional[List[str]] = None, env_path: str = ".env"):
        self.env_path = env_path
        self._keys: List[str] = []
        self._current_index: int = 0
        self._exhausted_keys: Set[str] = set()
        self._custom_keys: bool = bool(keys)

        if keys:
            self._keys = [k.strip() for k in keys if k.strip()]
        else:
            self.reload_keys()

    def reload_keys(self) -> None:
        """Reloads keys from settings and directly from .env file."""
        if self._custom_keys:
            return

        keys_set = set()

        ordered_keys = []

        # Read directly from .env file to catch immediate changes
        if os.path.exists(self.env_path):
            env_vals = dotenv_values(self.env_path)
            env_keys_str = env_vals.get("NEWS_API_KEYS", "")
            if env_keys_str:
                for k in env_keys_str.split(","):
                    k_clean = k.strip()
                    if k_clean and k_clean not in keys_set:
                        keys_set.add(k_clean)
                        ordered_keys.append(k_clean)

            single_key = env_vals.get("NEWS_API_KEY", "")
            if single_key:
                k_clean = single_key.strip()
                if k_clean and k_clean not in keys_set:
                    keys_set.add(k_clean)
                    ordered_keys.append(k_clean)

        # Fallback to Settings
        settings = get_settings()
        for k in settings.get_api_keys():
            k_clean = k.strip()
            if k_clean and k_clean not in keys_set:
                keys_set.add(k_clean)
                ordered_keys.append(k_clean)

        if ordered_keys:
            self._keys = ordered_keys
            logger.info(f"Loaded {len(self._keys)} API key(s) into rotator pool.")
        else:
            logger.warning("No API keys found in settings or .env!")

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @property
    def current_index(self) -> int:
        return self._current_index

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._keys):
            self._current_index = index

    def get_current_key(self) -> str:
        if not self._keys:
            self.reload_keys()
        if not self._keys:
            raise ValueError("No NewsAPI keys available in rotator. Please add them to .env.")
        return self._keys[self._current_index % len(self._keys)]

    def rotate(self, reason: str = "rate limit") -> str:
        """Rotates to the next available API key."""
        old_key = self.get_current_key()
        self._exhausted_keys.add(old_key)

        # Try to reload keys in case user pasted new keys into .env
        self.reload_keys()

        # Find next key not in exhausted_keys
        start_idx = self._current_index
        for offset in range(1, len(self._keys) + 1):
            next_idx = (start_idx + offset) % len(self._keys)
            candidate = self._keys[next_idx]
            if candidate not in self._exhausted_keys:
                self._current_index = next_idx
                logger.info(
                    f"Rotated API key due to {reason}. Switched to key "
                    f"[{candidate[:8]}...] (index {self._current_index + 1}/{len(self._keys)})."
                )
                return candidate

        # If all known keys are exhausted, clear exhausted set if new attempt needed or rotate anyway
        self._current_index = (self._current_index + 1) % len(self._keys)
        next_key = self._keys[self._current_index]
        logger.warning(
            f"All {len(self._keys)} API keys have encountered issues. "
            f"Rotating to key [{next_key[:8]}...] after reason: {reason}."
        )
        return next_key
