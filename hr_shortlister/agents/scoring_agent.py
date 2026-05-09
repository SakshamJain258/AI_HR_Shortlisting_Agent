from __future__ import annotations

import json

from hr_shortlister.core.llm_client import LLMQuotaError, LLMResponseError, generate_structured_json
from hr_shortlister.core.prompts import SCORING_SYSTEM_PROMPT, scoring_user_prompt
from hr_shortlister.core.schemas import (
    CandidateProfile,
    DimensionScore,
    ParsedJD,
    ScoreBreakdown,
    ScoringResult,
    SemanticMatch,
)
from hr_shortlister.core.utils import clamp_score, sanitize_llm_input


def score_candidate(
    parsed_jd: ParsedJD,
    candidate: CandidateProfile,
    semantic_match: SemanticMatch,
) -> ScoringResult:
    jd_json = parsed_jd.model_dump_json(indent=2)
    candidate_json = json.dumps(_candidate_for_prompt(candidate), indent=2)

    try:
        result = generate_structured_json(
            ScoringResult,
            SCORING_SYSTEM_PROMPT,
            scoring_user_prompt(jd_json, candidate_json, semantic_match.semantic_similarity_score),
        )
    except (LLMQuotaError, LLMResponseError):
        result = score_candidate_locally(parsed_jd, candidate, semantic_match)

    result.candidate_name = candidate.name
    result.source = candidate.source
    result.semantic_similarity = semantic_match.semantic_similarity_score
    return ScoringResult.model_validate(result.model_dump())


def score_candidate_locally(
    parsed_jd: ParsedJD,
    candidate: CandidateProfile,
    semantic_match: SemanticMatch,
) -> ScoringResult:
    required = {skill.casefold() for skill in parsed_jd.required_skills}
    preferred = {skill.casefold() for skill in parsed_jd.preferred_skills}
    candidate_skills = {skill.casefold() for skill in candidate.skills}

    required_ratio = len(required & candidate_skills) / len(required) if required else 0.5
    preferred_ratio = len(preferred & candidate_skills) / len(preferred) if preferred else 0.0
    skills_score = clamp_score((required_ratio * 8.0) + (preferred_ratio * 2.0))
    if semantic_match.semantic_similarity_score:
        skills_score = clamp_score((skills_score * 0.65) + (semantic_match.semantic_similarity_score * 0.35))

    required_exp = parsed_jd.min_experience_years or 0
    if required_exp <= 0:
        experience_score = 8.0 if candidate.projects or candidate.experiences else 6.0
    else:
        experience_score = clamp_score((candidate.experience_years / required_exp) * 8.0)

    education_score = 5.0
    if candidate.education:
        education_score += 2.0
    if candidate.certifications:
        education_score += 1.5
    if parsed_jd.education_requirement and candidate.education:
        education_score += 1.0

    project_score = 4.0 + min(len(candidate.projects), 3) * 1.5
    if any(required_skill in " ".join(project.description or "" for project in candidate.projects).casefold() for required_skill in required):
        project_score += 1.0

    communication_score = 6.0
    raw_text_length = len(candidate.raw_text or "")
    if raw_text_length > 1000:
        communication_score += 1.0
    if candidate.email or candidate.phone or candidate.linkedin_url:
        communication_score += 1.0

    scores = ScoreBreakdown(
        skills_match=DimensionScore(
            score=clamp_score(skills_score),
            justification="Local fallback: based on required/preferred skill overlap and semantic similarity.",
        ),
        experience_relevance=DimensionScore(
            score=clamp_score(experience_score),
            justification="Local fallback: based on stated years, projects, and work history.",
        ),
        education_certs=DimensionScore(
            score=clamp_score(education_score),
            justification="Local fallback: based on education and certifications found in the profile.",
        ),
        project_portfolio=DimensionScore(
            score=clamp_score(project_score),
            justification="Local fallback: based on project count and relevance signals.",
        ),
        communication_quality=DimensionScore(
            score=clamp_score(communication_score),
            justification="Local fallback: based on resume/profile completeness and contact details.",
        ),
    )

    return ScoringResult(
        candidate_name=candidate.name,
        source=candidate.source,
        scores=scores,
        semantic_similarity=semantic_match.semantic_similarity_score,
        summary="Generated with local fallback scoring because Gemini quota was unavailable.",
    )


def _candidate_for_prompt(candidate: CandidateProfile) -> dict:
    data = candidate.model_dump(mode="json")
    if data.get("raw_text"):
        data["raw_text"] = sanitize_llm_input(data["raw_text"], max_chars=8000)
    return data
