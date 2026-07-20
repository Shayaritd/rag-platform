"""
Model fallback router: Gemini is primary, Llama 3 (local/self-hosted, e.g.
via Ollama) is the fallback when Gemini errors, times out, or hits a rate
limit. A small in-process circuit breaker stops hammering Gemini once it's
clearly down, and recovers automatically after a cool-down window.
"""
import time
import logging
import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at: float | None = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at > self.cooldown_seconds:
            # half-open: allow a trial request through
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None


gemini_breaker = CircuitBreaker()


class GenerationResult:
    def __init__(self, text: str, provider: str):
        self.text = text
        self.provider = provider


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    resp = model.generate_content(prompt, request_options={"timeout": settings.LLM_TIMEOUT_SECONDS})
    return resp.text


def _call_llama(prompt: str) -> str:
    """Talks to a self-hosted/local Llama 3 endpoint (Ollama-compatible API)."""
    resp = httpx.post(
        f"{settings.LLAMA_BASE_URL}/api/generate",
        json={"model": settings.LLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def generate(prompt: str) -> GenerationResult:
    """Try Gemini first (unless the breaker is open), retry a couple of times,
    then fall back to Llama 3 on any failure so a query never hard-fails
    just because one provider is having a bad day."""
    if settings.GEMINI_API_KEY and not gemini_breaker.is_open():
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                text = _call_gemini(prompt)
                gemini_breaker.record_success()
                return GenerationResult(text=text, provider="gemini")
            except Exception as exc:
                logger.warning("Gemini attempt %s failed: %s", attempt, exc)
                gemini_breaker.record_failure()
                if gemini_breaker.is_open():
                    break
    try:
        text = _call_llama(prompt)
        return GenerationResult(text=text, provider="llama3")
    except Exception as exc:
        logger.error("Llama fallback also failed: %s", exc)
        raise RuntimeError("All LLM providers are unavailable") from exc
