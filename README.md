# HR Resume & LinkedIn Shortlisting Agent

A Streamlit-based HR evaluation dashboard that parses a job description, ingests resume files and LinkedIn profile URLs, compares candidates semantically against the role, scores them across an HR rubric, supports manual HR overrides, and generates a downloadable PDF report.

## What This Project Does

This project automates the first-pass shortlisting workflow for recruiters and HR teams.

The app supports:

- Job description input by pasted text or `.txt` / `.pdf` upload.
- Resume upload in `.pdf` and `.docx` formats.
- LinkedIn profile ingestion through RockApis on RapidAPI.
- Structured parsing with Gemini and Pydantic validation.
- Local fallback parsing and scoring when Gemini quota is unavailable.
- Semantic matching with `sentence-transformers`.
- Weighted HR scoring across 5 dimensions.
- Ranked dashboard results.
- HR override workflow with audit logging.
- Professional PDF report generation with ReportLab.

## Current Project Structure

```text
Resume Shortlister/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── hr_shortlister/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── jd_parser.py
│   │   ├── resume_parser.py
│   │   ├── linkedin_fetcher.py
│   │   ├── semantic_matcher.py
│   │   └── scoring_agent.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── llm_client.py
│   │   └── utils.py
│   └── services/
│       ├── __init__.py
│       ├── report_generator.py
│       └── override_logger.py
├── data/
│   ├── reports/
│   │   └── .gitkeep
│   └── overrides/
│       └── .gitkeep
└── docs/
    └── PROJECT_DOCUMENTATION.md
```

## Tech Stack

| Area | Tooling |
|---|---|
| UI | Streamlit |
| LLM parsing/scoring | Gemini API via `google-generativeai` |
| Validation | Pydantic v2 |
| PDF parsing | PyMuPDF |
| DOCX parsing | python-docx |
| LinkedIn scraping | RockApis LinkedIn Data API on RapidAPI |
| Semantic similarity | sentence-transformers `all-MiniLM-L6-v2` |
| Vector math | NumPy |
| PDF reports | ReportLab |
| Environment config | python-dotenv |

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

RAPIDAPI_KEY=your_rapidapi_key_here
RAPIDAPI_LINKEDIN_HOST=linkedin-data-api.p.rapidapi.com
RAPIDAPI_LINKEDIN_PROFILE_PATH=/get-profile-data-by-url
```

Important: never commit `.env`. It is ignored by `.gitignore`.

## Run The App

```powershell
streamlit run app.py
```

The app opens in your browser, usually at:

```text
http://localhost:8501
```

## End-To-End Workflow

1. HR enters or uploads a job description.
2. HR uploads candidate resumes and/or enters LinkedIn profile URLs.
3. `JD Parser Agent` extracts role requirements into `ParsedJD`.
4. `Resume Parser Agent` extracts candidate details from PDF/DOCX resumes.
5. `LinkedIn Fetcher Agent` fetches and maps RockApis profile JSON.
6. `Semantic Matcher` compares JD requirements with candidate evidence.
7. `Scoring Agent` scores candidates across the HR rubric.
8. Results are ranked by weighted total.
9. HR may override any score with a mandatory reason.
10. A PDF report is generated or regenerated after overrides.

## Scoring Rubric

The scoring model uses 5 dimensions:

| Dimension | Weight |
|---|---:|
| Skills Match | 30% |
| Experience Relevance | 25% |
| Education & Certs | 15% |
| Project / Portfolio | 20% |
| Communication Quality | 10% |

Recommendation thresholds:

| Weighted Score | Recommendation |
|---:|---|
| `>= 8.0` | HIRE |
| `6.0 - 7.9` | MAYBE |
| `< 6.0` | NO HIRE |

The weighted total is calculated in Python, not by the LLM.

## Gemini Fallback Behavior

The app first tries Gemini for structured parsing and scoring. If Gemini is unavailable because of quota, model availability, or response validation issues, the app falls back to local rule-based parsing/scoring so the workflow can continue.

Configured Gemini fallback models:

```text
gemini-2.5-flash
gemini-2.5-flash-lite
gemini-2.0-flash
gemini-2.0-flash-lite
gemini-1.5-flash-002
gemini-1.5-flash
```

## Generated Files

Generated runtime files are stored under `data/`:

```text
data/reports/      PDF reports
data/overrides/    override audit log
```

These generated files are ignored by Git. Only `.gitkeep` placeholders are committed.

## Security Notes

- `.env` and Streamlit secrets are ignored by Git.
- Candidate emails and phone numbers are masked in PDF reports.
- Prompt input is sanitized before being sent to Gemini.
- LLM outputs are validated by Pydantic.
- Scores are capped between 0 and 10.
- Final weighted totals are calculated deterministically in Python.

