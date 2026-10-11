"""Gemini client wrapper: automatic model selection, image + text prompts, strict JSON output.

Design rules
- The model never does arithmetic that matters: it reads the sheet into structured facts
  (tags, sizes, bar callouts, finish codes, counts) and the deterministic engines quantify.
- Vector text extracted from PDF/DXF is passed alongside the image so numbers are exact.
- Every call is schema-constrained (response_schema) and parsed into a pydantic model.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel

from app.config import get_settings
from app.models.schemas import AIStatus

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

PRO_PREFERENCE = ["gemini-3.1-pro", "gemini-3-pro", "gemini-2.5-pro", "gemini-2.0-pro", "gemini-1.5-pro"]
FAST_PREFERENCE = ["gemini-3.1-flash", "gemini-3-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
EXCLUDE_TOKENS = ("tts", "image", "live", "embedding", "audio", "native", "computer", "robotics", "lite", "thinking-exp", "8b")


class GeminiUnavailable(RuntimeError):
    pass


class GeminiClient:
    _instance: Optional["GeminiClient"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        s = get_settings()
        self.enabled = bool(s.gemini_api_key)
        self.model_fast: Optional[str] = None
        self.model_pro: Optional[str] = None
        self.message = ""
        self._client = None
        if not self.enabled:
            self.message = "GEMINI_API_KEY not set - AI reading disabled, deterministic extraction only."
            return
        try:
            from google import genai  # type: ignore
            from google.genai import types as _gt  # type: ignore
            # Hard HTTP timeout: a hung request must fail (and fall back) instead of blocking a worker forever.
            self._client = genai.Client(api_key=s.gemini_api_key,
                                        http_options=_gt.HttpOptions(timeout=int(s.gemini_timeout_s * 1000)))
            self._resolve_models(s.gemini_model_fast, s.gemini_model_pro)
            self.message = f"Gemini ready (fast={self.model_fast}, pro={self.model_pro})"
        except Exception as exc:  # pragma: no cover - network
            self.enabled = False
            self.message = f"Gemini init failed: {exc}"
            log.warning(self.message)

    # ------------------------------------------------------------------ setup
    @classmethod
    def get(cls) -> "GeminiClient":
        with cls._lock:
            if cls._instance is None:
                cls._instance = GeminiClient()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _list_model_names(self) -> List[str]:
        names: List[str] = []
        try:
            for m in self._client.models.list():  # type: ignore[union-attr]
                name = getattr(m, "name", "") or ""
                names.append(name.split("/")[-1])
        except Exception as exc:  # pragma: no cover - network
            log.warning("could not list Gemini models: %s", exc)
        return names

    @staticmethod
    def _pick(names: Sequence[str], prefs: Sequence[str]) -> Optional[str]:
        usable = [n for n in names if not any(t in n for t in EXCLUDE_TOKENS)]
        for pref in prefs:
            exact = [n for n in usable if n == pref]
            if exact:
                return exact[0]
            stable = [n for n in usable if n.startswith(pref) and "preview" not in n and "exp" not in n]
            if stable:
                return sorted(stable)[-1]
            previews = [n for n in usable if n.startswith(pref)]
            if previews:
                return sorted(previews)[-1]
        return None

    def _resolve_models(self, fast: str, pro: str) -> None:
        names = self._list_model_names() if (fast == "auto" or pro == "auto") else []
        self.model_fast = fast if fast != "auto" else (self._pick(names, FAST_PREFERENCE) or "gemini-2.5-flash")
        self.model_pro = pro if pro != "auto" else (self._pick(names, PRO_PREFERENCE) or self.model_fast)
        log.info("Gemini models: fast=%s pro=%s (from %d listed)", self.model_fast, self.model_pro, len(names))

    def status(self) -> AIStatus:
        return AIStatus(enabled=self.enabled, provider="gemini", model_fast=self.model_fast,
                        model_pro=self.model_pro, message=self.message)

    # ------------------------------------------------------------------ calls
    def generate_json(self, schema: Type[T], prompt: str, images: Sequence[bytes] = (),
                      tier: str = "pro", temperature: float = 0.1, max_output_tokens: int = 32768,
                      retries: int = 2, system: Optional[str] = None) -> T:
        if not self.enabled or self._client is None:
            raise GeminiUnavailable(self.message)
        from google.genai import types  # type: ignore

        model = self.model_pro if tier == "pro" else self.model_fast
        parts: List[Any] = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        parts.append(prompt)
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_output_tokens,
            system_instruction=system,
        )
        s = get_settings()
        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                t0 = time.time()
                resp = self._client.models.generate_content(model=model, contents=parts, config=config)
                text = resp.text or ""
                log.info("gemini %s: %d chars in %.1fs", model, len(text), time.time() - t0)
                parsed = getattr(resp, "parsed", None)
                if isinstance(parsed, schema):
                    return parsed
                return schema.model_validate(_loads_lenient(text))
            except Exception as exc:  # retry on transient / parse problems
                last_exc = exc
                log.warning("gemini attempt %d failed: %s", attempt + 1, exc)
                time.sleep(min(2 ** attempt, 8))
                if time.time() - t0 > s.gemini_timeout_s:
                    break
        raise GeminiUnavailable(f"Gemini call failed: {last_exc}")


def _loads_lenient(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # truncated output: try to close open brackets
        start = text.find("{")
        if start < 0:
            raise
        depth, end = 0, None
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
        if end:
            return json.loads(text[start:end])
        raise


def ai_status() -> AIStatus:
    return GeminiClient.get().status()
