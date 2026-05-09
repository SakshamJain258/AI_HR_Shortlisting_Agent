from __future__ import annotations

from functools import lru_cache

import numpy as np

from hr_shortlister.core.schemas import CandidateProfile, ParsedJD, SemanticMatch
from hr_shortlister.core.utils import clamp_score, sanitize_llm_input


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def calculate_semantic_match(parsed_jd: ParsedJD, candidate: CandidateProfile) -> SemanticMatch:
    jd_text = _jd_match_text(parsed_jd)
    candidate_text = _candidate_match_text(candidate)

    if not jd_text or not candidate_text:
        return SemanticMatch(semantic_similarity_score=0.0)

    model = _load_model()
    embeddings = model.encode([jd_text, candidate_text], normalize_embeddings=True)
    jd_embedding = np.asarray(embeddings[0], dtype=float)
    candidate_embedding = np.asarray(embeddings[1], dtype=float)

    cosine = float(np.dot(jd_embedding, candidate_embedding))
    score = clamp_score(max(0.0, cosine) * 10)

    return SemanticMatch(
        semantic_similarity_score=score,
        jd_embedding=jd_embedding.round(6).tolist(),
        candidate_embedding=candidate_embedding.round(6).tolist(),
    )


def _jd_match_text(parsed_jd: ParsedJD) -> str:
    parts = [
        parsed_jd.job_title,
        parsed_jd.domain,
        parsed_jd.seniority_level,
        " ".join(parsed_jd.required_skills),
        " ".join(parsed_jd.preferred_skills),
        " ".join(parsed_jd.key_responsibilities),
        parsed_jd.education_requirement,
        " ".join(parsed_jd.required_certifications),
    ]
    return sanitize_llm_input(" ".join(part for part in parts if part), max_chars=12000)


def _candidate_match_text(candidate: CandidateProfile) -> str:
    project_text = " ".join(
        " ".join(
            part
            for part in [
                project.name,
                project.description,
                " ".join(project.tech_stack),
            ]
            if part
        )
        for project in candidate.projects
    )
    education_text = " ".join(
        " ".join(part for part in [edu.degree, edu.institution] if part)
        for edu in candidate.education
    )
    experience_text = " ".join(
        " ".join(
            part
            for part in [
                experience.title,
                experience.company,
                experience.description,
            ]
            if part
        )
        for experience in candidate.experiences
    )
    parts = [
        " ".join(candidate.skills),
        " ".join(candidate.certifications),
        experience_text,
        project_text,
        education_text,
        candidate.raw_text,
    ]
    return sanitize_llm_input(" ".join(part for part in parts if part), max_chars=20000)


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Run pip install -r requirements.txt."
        ) from exc

    return SentenceTransformer(MODEL_NAME)
