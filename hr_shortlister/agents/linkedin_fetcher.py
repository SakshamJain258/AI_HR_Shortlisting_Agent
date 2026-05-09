from __future__ import annotations

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv

from hr_shortlister.core.schemas import (
    CandidateProfile,
    CandidateSource,
    Education,
    Project,
    WorkExperience,
)


DEFAULT_RAPIDAPI_HOST = "linkedin-data-api.p.rapidapi.com"
DEFAULT_PROFILE_PATH = "/get-profile-data-by-url"


def fetch_linkedin_profile(linkedin_url: str) -> CandidateProfile:
    load_dotenv()
    api_key = _get_secret("RAPIDAPI_KEY")
    if not api_key:
        raise RuntimeError("Missing RAPIDAPI_KEY in environment.")

    host = _get_secret("RAPIDAPI_LINKEDIN_HOST") or DEFAULT_RAPIDAPI_HOST
    profile_path = _get_secret("RAPIDAPI_LINKEDIN_PROFILE_PATH") or DEFAULT_PROFILE_PATH
    url = f"https://{host}{profile_path}"

    response = requests.get(
        url,
        headers={
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": host,
        },
        params={"url": linkedin_url},
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", payload)
    return map_linkedin_payload(data, linkedin_url)


def map_linkedin_payload(payload: dict[str, Any], linkedin_url: str) -> CandidateProfile:
    name = _first_text(
        payload,
        "full_name",
        "fullName",
        "name",
        "profile_name",
        "public_identifier",
    )
    if not name:
        first_name = _first_text(payload, "first_name", "firstName")
        last_name = _first_text(payload, "last_name", "lastName")
        name = " ".join(part for part in [first_name, last_name] if part).strip()

    education = [
        _map_education(item)
        for item in _as_list(_first_deep_value(payload, "educations", "education"))
    ]
    experiences = [
        _map_experience(item)
        for item in _as_list(
            _first_deep_value(payload, "fullPositions", "positions", "experience", "experiences")
        )
    ]
    projects = [_map_project(item) for item in _as_list(_first_deep_value(payload, "projects"))]

    skills = _extract_skills(payload)
    certifications = _extract_certifications(payload)
    location = _first_text(payload, "location", "city", "geo_location", "geo", "country_full_name")
    experience_years = _safe_float(
        _first_value(payload, "experience_years", "total_experience_years", "totalExperienceYears")
    )
    if experience_years == 0:
        experience_years = _estimate_experience_years([item for item in experiences if item])

    profile = CandidateProfile(
        source=CandidateSource.LINKEDIN,
        name=name or "Unknown Candidate",
        email=_first_text(payload, "email", "email_address"),
        phone=_first_text(payload, "phone", "phone_number"),
        location=location,
        education=[item for item in education if item],
        experiences=[item for item in experiences if item],
        experience_years=experience_years,
        skills=skills,
        certifications=certifications,
        projects=[item for item in projects if item],
        raw_text=json.dumps(payload, ensure_ascii=True),
        linkedin_url=linkedin_url,
    )
    return profile


def _map_education(item: Any) -> Education | None:
    if not isinstance(item, dict):
        return None
    return Education(
        degree=_first_text(item, "degree", "degreeName", "degree_name", "fieldOfStudy", "field_of_study"),
        institution=_first_text(item, "school", "schoolName", "school_name", "institution", "company"),
        year=_education_year(item),
        gpa=_safe_optional_float(_first_value(item, "gpa", "grade")),
    )


def _map_experience(item: Any) -> WorkExperience | None:
    if not isinstance(item, dict):
        return None

    title = _first_text(item, "title", "position", "role")
    company = _first_text(item, "companyName", "company_name", "company", "organization")
    description = _first_text(item, "description", "summary")
    if not any([title, company, description]):
        return None

    return WorkExperience(
        title=title,
        company=company,
        start_date=_date_text(_first_value(item, "start", "startDate", "startedOn")),
        end_date=_date_text(_first_value(item, "end", "endDate", "endedOn")) or "Present",
        description=description,
    )


def _map_project(item: Any) -> Project | None:
    if isinstance(item, str) and item.strip():
        return Project(name=item.strip())
    if not isinstance(item, dict):
        return None
    name = _first_text(item, "name", "title")
    if not name:
        return None
    return Project(
        name=name,
        description=_first_text(item, "description", "summary"),
        tech_stack=_normalize_text_list(_first_value(item, "tech_stack", "technologies", "skills")),
    )


def _extract_skills(payload: dict[str, Any]) -> list[str]:
    values = _first_value(payload, "skills", "top_skills", "skill")
    skills = _normalize_text_list(values)
    if skills:
        return skills

    about = _first_text(payload, "headline", "summary", "about")
    return _keyword_guess(about)


def _extract_certifications(payload: dict[str, Any]) -> list[str]:
    values = _first_deep_value(payload, "certifications", "licensesAndCertifications", "licenses_and_certifications")
    certifications: list[str] = []
    for item in _as_list(values):
        if isinstance(item, str):
            certifications.append(item)
        elif isinstance(item, dict):
            text = _first_text(item, "name", "title", "license_name")
            if text:
                certifications.append(text)
    return _dedupe(certifications)


def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
    value = _first_value(payload, *keys)
    if value is None:
        return None
    if isinstance(value, dict):
        value = _first_value(value, "name", "text", "title", "full")
    text = str(value).strip()
    return text or None


def _first_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _deep_get(payload: dict[str, Any], key: str) -> Any:
    if key in payload:
        return payload[key]
    for value in payload.values():
        if isinstance(value, dict):
            found = _deep_get(value, key)
            if found is not None:
                return found
    return None


def _first_deep_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        found = _deep_get(payload, key)
        if found not in (None, ""):
            return found
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_text_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in _as_list(value):
        if isinstance(item, str):
            parts = [part.strip() for part in item.replace(";", ",").split(",")]
            items.extend(part for part in parts if part)
        elif isinstance(item, dict):
            text = _first_text(item, "name", "title", "skill")
            if text:
                items.append(text)
    return _dedupe(items)


def _keyword_guess(text: str | None) -> list[str]:
    if not text:
        return []
    known = [
        "Python",
        "Java",
        "JavaScript",
        "TypeScript",
        "React",
        "FastAPI",
        "Django",
        "LangChain",
        "LangGraph",
        "RAG",
        "LLM",
        "AWS",
        "Docker",
        "SQL",
        "Machine Learning",
    ]
    lowered = text.lower()
    return [skill for skill in known if skill.lower() in lowered]


def _dedupe(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def _safe_float(value: Any) -> float:
    result = _safe_optional_float(value)
    return result if result is not None else 0.0


def _safe_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _education_year(item: dict[str, Any]) -> str | None:
    direct = _first_text(item, "year", "end_year", "date_range")
    if direct:
        return direct
    end = _date_text(_first_value(item, "end", "endDate"))
    start = _date_text(_first_value(item, "start", "startDate"))
    if start and end:
        return f"{start} - {end}"
    return end or start


def _date_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        year = _first_value(value, "year")
        month = _first_value(value, "month")
        if year and month:
            return f"{year}-{int(month):02d}"
        if year:
            return str(year)
        text = _first_text(value, "text", "date")
        return text
    return str(value).strip() or None


def _estimate_experience_years(experiences: list[WorkExperience]) -> float:
    years: list[int] = []
    for experience in experiences:
        if experience.start_date:
            try:
                years.append(int(str(experience.start_date)[:4]))
            except ValueError:
                continue
    if not years:
        return 0.0

    from datetime import datetime

    return max(0.0, round(datetime.now().year - min(years), 1))


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
