from __future__ import annotations

from pathlib import Path
import re

from hr_shortlister.core.llm_client import LLMQuotaError, LLMResponseError, generate_structured_json
from hr_shortlister.core.prompts import JD_SYSTEM_PROMPT, jd_user_prompt
from hr_shortlister.core.schemas import ParsedJD
from hr_shortlister.core.utils import bounded_text_block, sanitize_llm_input


def parse_jd_text(raw_text: str) -> ParsedJD:
    cleaned = sanitize_llm_input(raw_text)
    if not cleaned:
        raise ValueError("Job description text is empty.")

    prompt_text = bounded_text_block("JOB_DESCRIPTION", cleaned)
    try:
        return generate_structured_json(ParsedJD, JD_SYSTEM_PROMPT, jd_user_prompt(prompt_text))
    except (LLMQuotaError, LLMResponseError):
        return parse_jd_text_locally(cleaned)


def parse_jd_text_locally(cleaned_text: str) -> ParsedJD:
    """Best-effort JD parser used when Gemini quota is unavailable."""

    title = _extract_title(cleaned_text)
    skills = _extract_known_skills(cleaned_text)
    responsibilities = _extract_responsibilities(cleaned_text)
    experience = _extract_min_experience(cleaned_text)
    education = _extract_education_requirement(cleaned_text)

    return ParsedJD(
        job_title=title,
        required_skills=skills,
        preferred_skills=[],
        min_experience_years=experience,
        education_requirement=education,
        required_certifications=[],
        key_responsibilities=responsibilities,
        domain=_guess_domain(cleaned_text, skills),
        seniority_level=_guess_seniority(cleaned_text),
    )


def extract_jd_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix == ".txt":
        return data.decode("utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to read PDF job descriptions.") from exc

        with fitz.open(stream=data, filetype="pdf") as document:
            return "\n".join(page.get_text("text") for page in document)

    raise ValueError("Unsupported JD file type. Upload a .txt or .pdf file.")


def _extract_title(text: str) -> str:
    patterns = [
        r"(?:job\s*title|role|position)\s*[:\-]\s*([^\n\r.]{3,80})",
        r"we\s+are\s+hiring\s+(?:an?\s+)?([^\n\r.]{3,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" -:")

    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:80] or "Untitled Role"


def _extract_known_skills(text: str) -> list[str]:
    known_skills = [
        "Python",
        "Java",
        "JavaScript",
        "TypeScript",
        "React",
        "Node.js",
        "FastAPI",
        "Django",
        "Flask",
        "SQL",
        "PostgreSQL",
        "MongoDB",
        "AWS",
        "Azure",
        "GCP",
        "Docker",
        "Kubernetes",
        "LangChain",
        "LangGraph",
        "RAG",
        "LLM",
        "LLMs",
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "Qdrant",
        "Pinecone",
        "Streamlit",
        "Git",
    ]
    lowered = text.lower()
    return [skill for skill in known_skills if skill.lower() in lowered]


def _extract_responsibilities(text: str) -> list[str]:
    responsibilities: list[str] = []
    for line in re.split(r"[\n\r]+", text):
        cleaned = line.strip(" -•\t")
        if len(cleaned) < 12:
            continue
        if re.search(r"\b(develop|build|design|implement|manage|create|integrate|maintain|analyze)\b", cleaned, re.I):
            responsibilities.append(cleaned[:180])
        if len(responsibilities) >= 6:
            break
    return responsibilities


def _extract_min_experience(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else 0.0


def _extract_education_requirement(text: str) -> str | None:
    match = re.search(
        r"((?:B\.?Tech|M\.?Tech|Bachelor'?s?|Master'?s?|degree)[^.\n\r]{0,120})",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _guess_domain(text: str, skills: list[str]) -> str | None:
    lowered = text.lower()
    if {"LangChain", "RAG", "LLM", "LLMs"} & set(skills) or "artificial intelligence" in lowered:
        return "AI/ML Engineering"
    if "frontend" in lowered or "react" in lowered:
        return "Frontend Engineering"
    if "backend" in lowered or "api" in lowered:
        return "Backend Engineering"
    return None


def _guess_seniority(text: str) -> str | None:
    lowered = text.lower()
    for level in ["intern", "junior", "associate", "senior", "lead", "manager"]:
        if level in lowered:
            return level.title()
    return None
