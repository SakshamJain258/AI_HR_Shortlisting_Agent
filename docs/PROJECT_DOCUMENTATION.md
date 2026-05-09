# Project Documentation

## 1. Project Summary

The HR Resume & LinkedIn Shortlisting Agent is an end-to-end candidate evaluation workflow. It gives HR users a dashboard where they can enter a job description, upload resumes, add LinkedIn URLs, run automated analysis, review ranked results, override scores, and export a PDF report.

The project was built as a modular Python application with a Streamlit UI and a package named `hr_shortlister`.

## 2. What We Built

We implemented:

- A Streamlit dashboard with enhanced UI sections.
- A structured package layout.
- Job description parsing.
- Resume parsing from PDF and DOCX.
- LinkedIn profile fetching using RockApis on RapidAPI.
- Candidate normalization into a shared schema.
- Semantic similarity scoring using local embeddings.
- Gemini-based HR scoring with strict Pydantic validation.
- Local fallback parsing and scoring when Gemini cannot be used.
- HR override handling with audit logging.
- PDF report generation.
- GitHub-ready cleanup with `.gitignore`, `.env.example`, and documentation.

## 3. Why The Project Is Structured This Way

The project is split into three main package areas:

```text
hr_shortlister/agents/
```

Contains workflow nodes. These are the pieces that perform actual candidate analysis.

```text
hr_shortlister/core/
```

Contains shared contracts and utilities used by multiple agents.

```text
hr_shortlister/services/
```

Contains non-agent services such as PDF generation and override logging.

This keeps the UI separate from the business logic. `app.py` orchestrates the workflow, while the package modules do the real processing.

## 4. Main Files And Responsibilities

### `app.py`

The Streamlit entry point.

Responsibilities:

- Render the HR dashboard.
- Accept JD text/files.
- Accept resume uploads.
- Accept LinkedIn URLs.
- Show run readiness and progress.
- Call all agent modules in sequence.
- Render ranked results.
- Render candidate evidence cards.
- Render the Results PDF section.
- Render the HR override form.

### `hr_shortlister/core/schemas.py`

Defines Pydantic models used across the project.

Important models:

- `ParsedJD`
- `CandidateProfile`
- `Education`
- `WorkExperience`
- `Project`
- `SemanticMatch`
- `DimensionScore`
- `ScoreBreakdown`
- `ScoringResult`
- `OverrideRequest`
- `OverrideLogEntry`

This file acts as the project contract layer.

### `hr_shortlister/core/llm_client.py`

Handles Gemini calls.

Responsibilities:

- Load API keys from `.env` or Streamlit secrets.
- Send prompts to Gemini.
- Force JSON-style responses when supported.
- Extract JSON from model output.
- Validate responses against Pydantic schemas.
- Retry invalid responses.
- Try fallback Gemini models.
- Raise clear errors when quota or model availability fails.

### `hr_shortlister/core/prompts.py`

Stores prompts used for:

- JD parsing.
- Resume parsing.
- Candidate scoring.

Keeping prompts separate makes prompt iteration easier.

### `hr_shortlister/core/utils.py`

Shared helpers:

- LLM input sanitization.
- Directory creation.
- Safe filenames.
- Timestamp generation.
- Email masking.
- Phone masking.
- Score clamping.

### `hr_shortlister/agents/jd_parser.py`

Parses job descriptions.

Primary path:

1. Clean JD text.
2. Send JD to Gemini.
3. Validate output as `ParsedJD`.

Fallback path:

If Gemini fails, a local parser extracts:

- title
- known skills
- responsibilities
- minimum experience
- education requirement
- domain
- seniority

### `hr_shortlister/agents/resume_parser.py`

Parses resume files.

PDF parsing:

- Uses PyMuPDF.

DOCX parsing:

- Uses python-docx.

Primary path:

1. Extract raw text.
2. Send text to Gemini.
3. Validate output as `CandidateProfile`.

Fallback path:

If Gemini fails, a local parser extracts:

- candidate name
- email
- phone
- skills
- certifications
- project signals
- experience years

### `hr_shortlister/agents/linkedin_fetcher.py`

Fetches LinkedIn profile data using RockApis on RapidAPI.

Default API settings:

```env
RAPIDAPI_LINKEDIN_HOST=linkedin-data-api.p.rapidapi.com
RAPIDAPI_LINKEDIN_PROFILE_PATH=/get-profile-data-by-url
```

The API response is mapped into the same `CandidateProfile` model used by resumes. This means the rest of the pipeline does not care whether a candidate came from a resume or LinkedIn.

Mapped LinkedIn fields include:

- name
- location
- education
- work positions
- skills
- certifications
- projects
- raw profile JSON

### `hr_shortlister/agents/semantic_matcher.py`

Calculates semantic similarity between the JD and candidate profile.

How it works:

1. Convert JD skills, responsibilities, title, domain, and education into text.
2. Convert candidate skills, projects, education, experience, and raw text into text.
3. Generate embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
4. Calculate cosine similarity.
5. Convert similarity into a 0-10 score.

This score supports the Skills Match dimension.

### `hr_shortlister/agents/scoring_agent.py`

Scores a candidate against the JD.

Primary path:

1. Send `ParsedJD`, `CandidateProfile`, and semantic score to Gemini.
2. Gemini returns strict JSON.
3. Pydantic validates the response.
4. Python recalculates weighted total and recommendation.

Fallback path:

If Gemini fails, local scoring estimates:

- skill overlap
- experience relevance
- education/certifications
- projects
- communication completeness

### `hr_shortlister/services/report_generator.py`

Generates the PDF report using ReportLab.

PDF includes:

- cover page
- executive summary table
- candidate pages
- score charts
- dimension justifications
- recommendation badge
- HR override notes

Reports are written to:

```text
data/reports/
```

### `hr_shortlister/services/override_logger.py`

Handles HR score overrides.

When HR overrides a score:

1. Original score is captured.
2. New score is applied.
3. Weighted total is recalculated.
4. Recommendation is recalculated.
5. Override entry is appended to:

```text
data/overrides/log.json
```

## 5. Data Flow

```text
Streamlit UI
│
├── Job Description
│   └── JD Parser Agent
│       └── ParsedJD
│
├── Resume Files
│   └── Resume Parser Agent
│       └── CandidateProfile
│
├── LinkedIn URLs
│   └── LinkedIn Fetcher Agent
│       └── CandidateProfile
│
├── ParsedJD + CandidateProfile
│   └── Semantic Matcher
│       └── SemanticMatch
│
├── ParsedJD + CandidateProfile + SemanticMatch
│   └── Scoring Agent
│       └── ScoringResult
│
├── Ranked Results
│   ├── Streamlit Dashboard
│   ├── HR Override
│   └── PDF Report Generator
```

## 6. Scoring Formula

Each score is between 0 and 10.

```python
weighted_total = (
    skills_match * 0.30
    + experience_relevance * 0.25
    + education_certs * 0.15
    + project_portfolio * 0.20
    + communication_quality * 0.10
)
```

Recommendation:

- `>= 7.0`: `HIRE`
- `4.0 - 6.9`: `MAYBE`
- `< 4.0`: `NO HIRE`

## 7. UI Features

The UI is not just a basic Streamlit form. It includes:

- dashboard header
- intake workspace
- JD and candidate tabs
- run-control side panel
- readiness metrics
- parsed role snapshot
- shortlist summary cards
- ranked table
- visual candidate cards
- dimension score bars
- expandable evidence panels
- Results PDF section
- HR override section

## 8. Security And Privacy

Security measures implemented:

- `.env` ignored by Git.
- Streamlit secrets ignored by Git.
- `.env.example` uses placeholders only.
- Candidate contact details are masked in generated reports.
- Prompt input is sanitized.
- LLM outputs are validated with Pydantic.
- Extra LLM output fields are rejected.
- Weighted total is calculated in Python.
- Runtime generated reports/logs are ignored by Git.

## 9. Known Limitations

- LinkedIn scraping depends on RapidAPI quota and endpoint availability.
- Gemini parsing/scoring depends on Google API quota.
- Local fallback parsing is useful but less accurate than Gemini.
- Semantic embeddings download/load the first time `sentence-transformers` is used.
- PDF/DOCX extraction quality depends on the formatting of uploaded files.

## 10. Future Improvements

Possible next steps:

- Add tests for each agent.
- Add CSV export.
- Add recruiter notes per candidate.
- Add batch resume duplicate detection.
- Add configurable scoring weights from UI.
- Add support for more resume formats.
- Add database persistence.
- Add authentication with user accounts.
- Add LangGraph orchestration around the current node flow.

