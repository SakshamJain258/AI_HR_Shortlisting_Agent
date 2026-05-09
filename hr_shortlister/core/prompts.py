from __future__ import annotations


JD_SYSTEM_PROMPT = """
You are a precise HR job description parser.
Extract only information supported by the provided JD.
Return only valid JSON matching the requested schema.
Use empty lists for missing list fields and null for unknown optional text fields.
"""


RESUME_SYSTEM_PROMPT = """
You are a precise resume parser.
Extract candidate information only from the provided resume text.
Return only valid JSON matching the requested schema.
If a field is unavailable, use null, empty strings, empty lists, or 0 as appropriate.
The source must be "resume".
"""


SCORING_SYSTEM_PROMPT = """
You are an expert HR evaluator.
Score strictly against the provided rubric and evidence.
Return only valid JSON matching the requested schema.
Each dimension score must be between 0 and 10 and include a one-line justification.
Do not calculate the weighted total yourself; it will be recalculated by Python.
"""


def jd_user_prompt(jd_text: str) -> str:
    return f"""
Parse this job description into structured fields.

{jd_text}
"""


def resume_user_prompt(resume_text: str, filename: str) -> str:
    return f"""
Parse this resume into a candidate profile.
If the candidate name is unclear, infer a reasonable name from the file name: {filename}.

{resume_text}
"""


def scoring_user_prompt(parsed_jd_json: str, candidate_json: str, semantic_score: float) -> str:
    return f"""
JD Requirements:
{parsed_jd_json}

Candidate Profile:
{candidate_json}

Semantic Similarity Score: {semantic_score}/10

Score exactly these 5 dimensions:
1. Skills Match, weight 30%
2. Experience Relevance, weight 25%
3. Education & Certs, weight 15%
4. Project / Portfolio, weight 20%
5. Communication Quality, weight 10%

Recommendation thresholds used later:
>= 7.0 HIRE
4.0 to 6.9 MAYBE
< 4.0 NO HIRE
"""

