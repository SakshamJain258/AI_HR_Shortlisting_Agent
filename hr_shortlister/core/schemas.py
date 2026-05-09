from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ScoreName = Literal[
    "skills_match",
    "experience_relevance",
    "education_certs",
    "project_portfolio",
    "communication_quality",
]


class StrictBaseModel(BaseModel):
    """Base model used for all LLM-facing schemas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Recommendation(str, Enum):
    HIRE = "HIRE"
    MAYBE = "MAYBE"
    NO_HIRE = "NO HIRE"


class CandidateSource(str, Enum):
    RESUME = "resume"
    LINKEDIN = "linkedin"


class ParsedJD(StrictBaseModel):
    job_title: str = Field(..., min_length=1)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_years: float = Field(default=0, ge=0)
    education_requirement: str | None = None
    required_certifications: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    domain: str | None = None
    seniority_level: str | None = None

    @field_validator(
        "required_skills",
        "preferred_skills",
        "required_certifications",
        "key_responsibilities",
        mode="before",
    )
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise ValueError("Expected a list of strings.")

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            key = text.casefold()
            if text and key not in seen:
                cleaned.append(text)
                seen.add(key)
        return cleaned


class Education(StrictBaseModel):
    degree: str | None = None
    institution: str | None = None
    year: str | None = None
    gpa: float | None = Field(default=None, ge=0, le=100)


class Project(StrictBaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    tech_stack: list[str] = Field(default_factory=list)

    @field_validator("tech_stack", mode="before")
    @classmethod
    def normalize_tech_stack(cls, value: Any) -> list[str]:
        return ParsedJD.normalize_string_list(value)


class WorkExperience(StrictBaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class CandidateProfile(StrictBaseModel):
    source: CandidateSource
    name: str = Field(default="Unknown Candidate", min_length=1)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    education: list[Education] = Field(default_factory=list)
    experiences: list[WorkExperience] = Field(default_factory=list)
    experience_years: float = Field(default=0, ge=0)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    raw_text: str | None = None
    linkedin_url: str | None = None

    @field_validator("skills", "certifications", mode="before")
    @classmethod
    def normalize_profile_lists(cls, value: Any) -> list[str]:
        return ParsedJD.normalize_string_list(value)

    @model_validator(mode="after")
    def require_profile_signal(self) -> CandidateProfile:
        has_contact = bool(self.email or self.phone or self.linkedin_url)
        has_content = bool(
            self.skills or self.education or self.experiences or self.projects or self.raw_text
        )
        if not has_contact and not has_content:
            raise ValueError("Candidate profile must include contact or profile content.")
        return self


class SemanticMatch(StrictBaseModel):
    semantic_similarity_score: float = Field(..., ge=0, le=10)
    jd_embedding: list[float] = Field(default_factory=list)
    candidate_embedding: list[float] = Field(default_factory=list)


class DimensionScore(StrictBaseModel):
    score: float = Field(..., ge=0, le=10)
    justification: str = Field(..., min_length=1)


class ScoreBreakdown(StrictBaseModel):
    skills_match: DimensionScore
    experience_relevance: DimensionScore
    education_certs: DimensionScore
    project_portfolio: DimensionScore
    communication_quality: DimensionScore

    def weighted_total(self) -> float:
        total = sum(
            getattr(self, name).score * weight for name, weight in ScoringResult.WEIGHTS.items()
        )
        return round(total, 2)


class ScoringResult(StrictBaseModel):
    WEIGHTS: ClassVar[dict[ScoreName, float]] = {
        "skills_match": 0.30,
        "experience_relevance": 0.25,
        "education_certs": 0.15,
        "project_portfolio": 0.20,
        "communication_quality": 0.10,
    }

    candidate_name: str = Field(..., min_length=1)
    source: CandidateSource | None = None
    scores: ScoreBreakdown
    weighted_total: float = Field(default=0, ge=0, le=10)
    recommendation: Recommendation = Recommendation.MAYBE
    semantic_similarity: float = Field(..., ge=0, le=10)
    summary: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def calculate_total_and_recommendation(self) -> ScoringResult:
        self.weighted_total = self.scores.weighted_total()
        self.recommendation = recommendation_for_score(self.weighted_total)
        return self


class OverrideRequest(StrictBaseModel):
    candidate: str = Field(..., min_length=1)
    dimension: ScoreName
    new_score: float = Field(..., ge=0, le=10)
    reason: str = Field(..., min_length=1)


class OverrideLogEntry(OverrideRequest):
    timestamp: datetime = Field(default_factory=datetime.now)
    original_score: float = Field(..., ge=0, le=10)
    hr_action: Literal["score_adjusted"] = "score_adjusted"


def recommendation_for_score(weighted_total: float) -> Recommendation:
    if weighted_total >= 8.0:
        return Recommendation.HIRE
    if weighted_total >= 6.0:
        return Recommendation.MAYBE
    return Recommendation.NO_HIRE
