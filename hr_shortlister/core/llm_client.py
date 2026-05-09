from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)
MODEL_FALLBACKS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash",
]


class LLMConfigError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMQuotaError(LLMResponseError):
    pass


def generate_structured_json(
    schema: type[T],
    system_prompt: str,
    user_prompt: str,
    *,
    max_retries: int = 3,
    temperature: float = 0.1,
) -> T:
    """Ask Gemini for JSON and validate it against a Pydantic model."""

    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    validation_hint = ""
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        prompt = f"""
{system_prompt}

Return JSON matching this schema:
{schema_json}

{validation_hint}

{user_prompt}
"""
        try:
            raw = _generate_with_gemini(prompt, temperature=temperature)
            parsed = _extract_json(raw)
            return schema.model_validate(parsed)
        except (LLMQuotaError, LLMResponseError):
            raise
        except (json.JSONDecodeError, ValidationError, LLMResponseError) as exc:
            last_error = exc
            validation_hint = (
                "The previous response failed JSON/schema validation. "
                f"Retry with valid JSON only. Validation error: {exc}"
            )

    raise LLMResponseError(f"Gemini did not return valid {schema.__name__}: {last_error}")


def _generate_with_gemini(prompt: str, *, temperature: float) -> str:
    load_dotenv()

    api_key = _get_secret("GEMINI_API_KEY") or _get_secret("GOOGLE_API_KEY")
    if not api_key:
        raise LLMConfigError(
            "Missing GEMINI_API_KEY or GOOGLE_API_KEY. Add it to a .env file or Streamlit secrets."
        )

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise LLMConfigError("google-generativeai is not installed. Run pip install -r requirements.txt.") from exc

    genai.configure(api_key=api_key)
    configured_model = _get_secret("GEMINI_MODEL") or MODEL_FALLBACKS[0]
    model_names = [configured_model] + [name for name in MODEL_FALLBACKS if name != configured_model]
    last_error: Exception | None = None

    for model_name in model_names:
        model = genai.GenerativeModel(model_name)
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                },
            )
            break
        except TypeError:
            try:
                response = model.generate_content(prompt)
                break
            except Exception as exc:
                last_error = exc
                if _should_try_next_model(exc):
                    continue
                raise
        except Exception as exc:
            last_error = exc
            if _should_try_next_model(exc):
                continue
            raise
    else:
        error_cls = LLMQuotaError if last_error and _is_quota_error(last_error) else LLMResponseError
        raise error_cls(
            "None of the configured Gemini models are available for generateContent. "
            f"Tried: {', '.join(model_names)}. Last error: {last_error}"
        )

    text = getattr(response, "text", None)
    if text:
        return text

    try:
        return response.candidates[0].content.parts[0].text
    except (AttributeError, IndexError) as exc:
        raise LLMResponseError("Gemini returned an empty response.") from exc


def _get_secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        secret = st.secrets.get(name, None)
        if secret:
            return str(secret)
    except Exception:
        return None

    return None


def _is_missing_model_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "404" in text
        and "model" in text
        and ("not found" in text or "not supported" in text)
    )


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "quota" in text or "rate limit" in text


def _should_try_next_model(exc: Exception) -> bool:
    return _is_missing_model_error(exc) or _is_quota_error(exc)


def _extract_json(raw: str) -> object:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])
