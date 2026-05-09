from __future__ import annotations

import html
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from hr_shortlister.agents.jd_parser import extract_jd_text, parse_jd_text
from hr_shortlister.agents.linkedin_fetcher import fetch_linkedin_profile
from hr_shortlister.agents.resume_parser import parse_resume_file
from hr_shortlister.agents.scoring_agent import score_candidate
from hr_shortlister.agents.semantic_matcher import calculate_semantic_match
from hr_shortlister.core.schemas import (
    CandidateProfile,
    OverrideRequest,
    ParsedJD,
    Recommendation,
    ScoringResult,
)
from hr_shortlister.services.override_logger import append_override_log, apply_override
from hr_shortlister.services.report_generator import DIMENSION_LABELS, generate_pdf_report


load_dotenv()

st.set_page_config(
    page_title="HR Shortlisting Agent",
    layout="wide",
)


def main() -> None:
    if not _check_password():
        return

    _init_state()
    _inject_css()

    _render_header()

    input_col, run_col = st.columns([1.35, 0.65], gap="large")
    with input_col:
        jd_text, jd_file, resumes, linkedin_urls_text = _render_input_workspace()
    with run_col:
        _render_run_panel(jd_text, jd_file, resumes, linkedin_urls_text)

    _render_results()


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 3rem;
            max-width: 1440px;
        }
        div[data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #eef5f4 0%, #f8fafc 280px, #ffffff 100%);
        }
        .hero, .panel, .metric-card, .result-card {
            border: 1px solid #d8dee9;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.055);
        }
        .hero {
            padding: 1.35rem 1.5rem;
            margin-bottom: 1rem;
        }
        .hero-kicker {
            color: #115e59;
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .hero h1 {
            color: #172033;
            font-size: 2rem;
            line-height: 1.15;
            margin: 0;
        }
        .hero p {
            color: #667085;
            margin: 0.55rem 0 0;
            max-width: 880px;
        }
        .panel {
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .panel-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.55rem;
        }
        .panel-title h2, .panel-title h3 {
            color: #172033;
            font-size: 1.04rem;
            line-height: 1.3;
            margin: 0;
        }
        .hint {
            color: #667085;
            font-size: 0.86rem;
            margin: 0;
        }
        .pill {
            border: 1px solid #b6d8d4;
            border-radius: 999px;
            color: #115e59;
            background: #eef8f6;
            font-size: 0.78rem;
            font-weight: 750;
            padding: 0.2rem 0.55rem;
            white-space: nowrap;
        }
        .metric-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 1rem 0;
        }
        .metric-card {
            padding: 0.85rem;
        }
        .metric-label {
            color: #667085;
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .metric-value {
            color: #172033;
            font-size: 1.45rem;
            font-weight: 850;
            line-height: 1.2;
            margin-top: 0.25rem;
            overflow-wrap: anywhere;
        }
        .mini-stat {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #fbfdff;
            padding: 0.75rem;
            margin: 0.75rem 0;
        }
        .result-card {
            padding: 1rem;
            margin-bottom: 0.85rem;
        }
        .result-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }
        .candidate-name {
            color: #172033;
            font-size: 1.12rem;
            font-weight: 850;
            margin: 0;
        }
        .candidate-meta {
            color: #667085;
            font-size: 0.86rem;
            margin-top: 0.2rem;
        }
        .badge {
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-size: 0.78rem;
            font-weight: 850;
            white-space: nowrap;
        }
        .badge-hire { color: #14532d; background: #dcfce7; border: 1px solid #86efac; }
        .badge-maybe { color: #713f12; background: #fef9c3; border: 1px solid #fde047; }
        .badge-no-hire { color: #7f1d1d; background: #fee2e2; border: 1px solid #fca5a5; }
        .score-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(110px, 1fr));
            gap: 0.65rem;
            margin-top: 0.75rem;
        }
        .score-cell {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.65rem;
            background: #fbfdff;
        }
        .score-title {
            color: #667085;
            font-size: 0.75rem;
            font-weight: 750;
            min-height: 2.1rem;
        }
        .score-number {
            color: #172033;
            font-size: 1.25rem;
            font-weight: 850;
            margin: 0.25rem 0;
        }
        .bar-track {
            height: 8px;
            border-radius: 999px;
            background: #e5e7eb;
            overflow: hidden;
        }
        .bar-fill {
            height: 8px;
            border-radius: 999px;
        }
        .summary-box {
            border-left: 4px solid #0f766e;
            background: #f0fdfa;
            padding: 0.75rem 0.85rem;
            border-radius: 6px;
            color: #134e4a;
            margin-top: 0.7rem;
        }
        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-top: 0.55rem;
        }
        .chip {
            border-radius: 999px;
            border: 1px solid #d8dee9;
            background: #f8fafc;
            color: #344054;
            font-size: 0.78rem;
            padding: 0.18rem 0.5rem;
        }
        .pdf-status {
            border: 1px solid #d8dee9;
            border-radius: 8px;
            background: #fbfdff;
            padding: 0.9rem;
            margin-bottom: 0.8rem;
        }
        .pdf-ready {
            border-color: #86efac;
            background: #f0fdf4;
        }
        .pdf-waiting {
            border-color: #fde68a;
            background: #fffbeb;
        }
        .pdf-title {
            color: #172033;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }
        .pdf-meta {
            color: #667085;
            font-size: 0.86rem;
            overflow-wrap: anywhere;
        }
        @media (max-width: 900px) {
            .metric-row, .score-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">HR Evaluation Workspace</div>
            <h1>Resume & LinkedIn Shortlisting Agent</h1>
            <p>Parse the role, evaluate resumes and LinkedIn profiles, review ranked evidence, apply HR overrides, and export a structured PDF report from one dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_input_workspace():
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">
                <h2>Candidate Intake</h2>
                <span class="pill">JD + resumes + LinkedIn</span>
            </div>
            <p class="hint">Use pasted text, uploaded files, or both. The pipeline merges resume and LinkedIn candidates into one ranked list.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    jd_tab, candidate_tab = st.tabs(["Job Description", "Candidates"])

    with jd_tab:
        jd_left, jd_right = st.columns([0.68, 0.32], gap="large")
        with jd_left:
            jd_text = st.text_area(
                "Paste job description",
                height=300,
                placeholder="Paste the complete job description here...",
            )
        with jd_right:
            jd_file = st.file_uploader("Upload JD file", type=["txt", "pdf"])
            st.markdown(_mini_stat("Typed JD Characters", f"{len(jd_text or ''):,}"), unsafe_allow_html=True)
            if jd_file:
                st.markdown(_mini_stat("JD File", jd_file.name), unsafe_allow_html=True)

    with candidate_tab:
        upload_col, linkedin_col = st.columns(2, gap="large")
        with upload_col:
            resumes = st.file_uploader(
                "Upload resumes",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                help="Upload 1 to 100 PDF/DOCX resumes.",
            )
            st.markdown(_mini_stat("Resume Files", str(len(resumes or []))), unsafe_allow_html=True)
        with linkedin_col:
            linkedin_urls_text = st.text_area(
                "LinkedIn profile URLs",
                height=170,
                placeholder="https://linkedin.com/in/username\nhttps://linkedin.com/in/another-profile",
            )
            st.markdown(
                _mini_stat("LinkedIn Profiles", str(len(_parse_linkedin_urls(linkedin_urls_text)))),
                unsafe_allow_html=True,
            )

    return jd_text, jd_file, resumes, linkedin_urls_text


def _render_run_panel(jd_text: str, jd_file, resumes: list, linkedin_urls_text: str) -> None:
    linkedin_urls = _parse_linkedin_urls(linkedin_urls_text)
    resume_count = len(resumes or [])
    has_jd = bool((jd_text or "").strip() or jd_file)
    candidate_count = resume_count + len(linkedin_urls)

    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">
                <h2>Run Control</h2>
                <span class="pill">Analysis queue</span>
            </div>
            <p class="hint">JD parsing runs first, then every candidate is scored and added to the ranked report.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="metric-row" style="grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 0;">
            {_metric_card("JD Ready", "Yes" if has_jd else "No")}
            {_metric_card("Candidates", str(candidate_count))}
            {_metric_card("Resumes", str(resume_count))}
            {_metric_card("LinkedIn", str(len(linkedin_urls)))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    can_run = has_jd and candidate_count > 0
    if not can_run:
        st.info("Add a job description and at least one candidate source to enable analysis.")

    if st.button("Analyse Candidates", type="primary", use_container_width=True, disabled=not can_run):
        _run_analysis(jd_text, jd_file, resumes, linkedin_urls_text)

    if st.session_state.parsed_jd:
        _render_jd_snapshot(st.session_state.parsed_jd)


def _check_password() -> bool:
    try:
        expected_password = st.secrets.get("APP_PASSWORD", None)
    except Exception:
        expected_password = None
    if not expected_password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("HR Shortlisting Agent")
    password = st.text_input("Password", type="password")
    if st.button("Sign in"):
        if password == expected_password:
            st.session_state.authenticated = True
            st.rerun()
        st.error("Invalid password.")
    return False


def _init_state() -> None:
    defaults = {
        "parsed_jd": None,
        "candidates": [],
        "results": [],
        "report_path": None,
        "candidate_errors": [],
        "current_overrides": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _run_analysis(jd_text: str, jd_file, resumes: list, linkedin_urls_text: str) -> None:
    st.session_state.candidates = []
    st.session_state.results = []
    st.session_state.report_path = None
    st.session_state.candidate_errors = []
    st.session_state.current_overrides = []

    try:
        raw_jd = _get_jd_text(jd_text, jd_file)
    except Exception as exc:
        st.error(f"Could not read job description: {exc}")
        return

    linkedin_urls = _parse_linkedin_urls(linkedin_urls_text)
    resumes = resumes or []
    if not raw_jd.strip():
        st.error("Please paste or upload a job description.")
        return
    if not resumes and not linkedin_urls:
        st.error("Please upload at least one resume or enter at least one LinkedIn URL.")
        return
    if len(resumes) > 100:
        st.error("Please upload 100 resumes or fewer in one run.")
        return

    total_steps = 1 + len(resumes) + len(linkedin_urls)
    progress = st.progress(0)
    status = st.empty()
    start_time = time.time()

    try:
        status.info("Parsing job description with Gemini...")
        parsed_jd = parse_jd_text(raw_jd)
        st.session_state.parsed_jd = parsed_jd
        progress.progress(1 / total_steps)
    except Exception as exc:
        progress.empty()
        status.empty()
        st.error(f"JD parsing failed: {exc}")
        return

    completed = 1
    for resume in resumes:
        label = getattr(resume, "name", "resume")
        status.info(f"Processing resume: {label} | ETA {_eta(start_time, completed, total_steps)}")
        try:
            candidate = parse_resume_file(resume.name, resume.getvalue())
            _score_and_store(parsed_jd, candidate)
        except Exception as exc:
            st.session_state.candidate_errors.append(f"{label}: {exc}")
        completed += 1
        progress.progress(completed / total_steps)

    for url in linkedin_urls:
        status.info(f"Processing LinkedIn profile: {url} | ETA {_eta(start_time, completed, total_steps)}")
        try:
            candidate = fetch_linkedin_profile(url)
            _score_and_store(parsed_jd, candidate)
        except Exception as exc:
            st.session_state.candidate_errors.append(f"{url}: {exc}")
        completed += 1
        progress.progress(completed / total_steps)

    st.session_state.results = _sorted_results(st.session_state.results)
    if st.session_state.results:
        st.session_state.report_path = generate_pdf_report(
            parsed_jd.job_title,
            st.session_state.results,
            st.session_state.candidates,
            st.session_state.current_overrides,
        )

    status.success("Analysis complete.")


def _score_and_store(parsed_jd: ParsedJD, candidate: CandidateProfile) -> None:
    semantic_match = calculate_semantic_match(parsed_jd, candidate)
    result = score_candidate(parsed_jd, candidate, semantic_match)
    st.session_state.candidates.append(candidate)
    st.session_state.results.append(result)


def _render_results() -> None:
    results: list[ScoringResult] = st.session_state.results
    if not results:
        if st.session_state.candidate_errors:
            _render_errors()
        return

    st.markdown("---")
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">
                <h2>Shortlist Dashboard</h2>
                <span class="pill">Ranked by weighted score</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_result_metrics(results)

    report_col, override_col = st.columns([0.42, 0.58], gap="large")
    with report_col:
        _render_report_panel()
    with override_col:
        _render_override_form(results)

    st.subheader("Ranked Results")
    rows = []
    for index, result in enumerate(results, start=1):
        rows.append(
            {
                "Rank": index,
                "Name": result.candidate_name,
                "Source": result.source.value.title() if result.source else "-",
                "Total Score": round(result.weighted_total, 2),
                "Semantic": round(result.semantic_similarity, 2),
                "Recommendation": result.recommendation.value,
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)

    _render_breakdowns(results)
    _render_errors()


def _render_result_metrics(results: list[ScoringResult]) -> None:
    hires = sum(1 for result in results if result.recommendation == Recommendation.HIRE)
    maybes = sum(1 for result in results if result.recommendation == Recommendation.MAYBE)
    no_hires = sum(1 for result in results if result.recommendation == Recommendation.NO_HIRE)
    avg_score = sum(result.weighted_total for result in results) / len(results)
    top_score = max(result.weighted_total for result in results)

    st.markdown(
        f"""
        <div class="metric-row">
            {_metric_card("Evaluated", str(len(results)))}
            {_metric_card("Shortlisted", str(hires))}
            {_metric_card("Average Score", f"{avg_score:.2f}")}
            {_metric_card("Top Score", f"{top_score:.2f}")}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Recommendation mix: {hires} hire, {maybes} maybe, {no_hires} no hire.")


def _render_report_panel() -> None:
    report_path = st.session_state.report_path
    report_ready = bool(report_path and Path(report_path).exists())
    result_count = len(st.session_state.results)
    override_count = len(st.session_state.current_overrides)

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">
                <h3>Results PDF</h3>
                <span class="pill">{'Ready for download' if report_ready else 'Waiting for results'}</span>
            </div>
            <p class="hint">The report is generated after analysis and regenerated automatically after each HR override.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if report_ready:
        path = Path(report_path)
        size_kb = path.stat().st_size / 1024
        st.markdown(
            f"""
            <div class="pdf-status pdf-ready">
                <div class="pdf-title">Report is ready</div>
                <div class="pdf-meta">File: {_escape(path.name)}</div>
                <div class="pdf-meta">Candidates: {result_count} | Overrides: {override_count} | Size: {size_kb:.1f} KB</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download PDF Report",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.markdown(
            """
            <div class="pdf-status pdf-waiting">
                <div class="pdf-title">Report not generated yet</div>
                <div class="pdf-meta">Run candidate analysis first. When the PDF is ready, this section will show the file details and download button.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_breakdowns(results: list[ScoringResult]) -> None:
    st.subheader("Candidate Evidence")
    for result in results:
        st.markdown(_candidate_card(result), unsafe_allow_html=True)
        with st.expander(f"View evidence and justifications for {result.candidate_name}"):
            candidate = _find_candidate(result.candidate_name)
            if candidate:
                _render_candidate_profile(candidate)

            for dimension in ScoringResult.WEIGHTS:
                score_item = getattr(result.scores, dimension)
                st.markdown(f"**{DIMENSION_LABELS[dimension]}:** {score_item.score:.1f}/10")
                st.caption(score_item.justification)


def _render_override_form(results: list[ScoringResult]) -> None:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">
                <h3>HR Override</h3>
                <span class="pill">Audit logged</span>
            </div>
            <p class="hint">Adjust a dimension score when human review finds evidence the automated workflow missed.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    labels = [f"{index}. {result.candidate_name}" for index, result in enumerate(results, start=1)]

    with st.form("override_form"):
        selected_label = st.selectbox("Candidate", labels)
        selected_index = labels.index(selected_label)
        selected_result = results[selected_index]

        dimension = st.selectbox(
            "Dimension to override",
            list(ScoringResult.WEIGHTS.keys()),
            format_func=lambda value: DIMENSION_LABELS[value],
        )
        current_score = getattr(selected_result.scores, dimension).score
        new_score = st.slider("New score", min_value=0.0, max_value=10.0, value=float(current_score), step=0.5)
        reason = st.text_input("Reason")
        submitted = st.form_submit_button("Apply Override", use_container_width=True)

    if not submitted:
        return

    if not reason.strip():
        st.error("Override reason is mandatory.")
        return

    request = OverrideRequest(
        candidate=selected_result.candidate_name,
        dimension=dimension,
        new_score=new_score,
        reason=reason,
    )
    updated, entry = apply_override(selected_result, request)
    st.session_state.results[selected_index] = updated
    st.session_state.results = _sorted_results(st.session_state.results)
    append_override_log(entry)
    st.session_state.current_overrides.append(entry.model_dump(mode="json"))

    parsed_jd: ParsedJD = st.session_state.parsed_jd
    st.session_state.report_path = generate_pdf_report(
        parsed_jd.job_title,
        st.session_state.results,
        st.session_state.candidates,
        st.session_state.current_overrides,
    )
    st.success("Override applied, weighted score recalculated, and PDF regenerated.")
    st.rerun()


def _render_errors() -> None:
    errors = st.session_state.candidate_errors
    if not errors:
        return
    with st.expander("Candidate processing errors", expanded=False):
        for error in errors:
            st.warning(error)


def _render_jd_snapshot(parsed_jd: ParsedJD) -> None:
    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">
                <h3>Parsed Role</h3>
                <span class="pill">{_escape(parsed_jd.seniority_level or "Role")}</span>
            </div>
            <div class="metric-label">Job Title</div>
            <div class="metric-value" style="font-size: 1.05rem;">{_escape(parsed_jd.job_title)}</div>
            <p class="hint" style="margin-top: 0.55rem;">Domain: {_escape(parsed_jd.domain or "-")} | Min exp: {parsed_jd.min_experience_years:g} years</p>
            {_chips(parsed_jd.required_skills[:8])}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_candidate_profile(candidate: CandidateProfile) -> None:
    profile_cols = st.columns(4)
    profile_cols[0].metric("Source", candidate.source.value.title())
    profile_cols[1].metric("Experience", f"{candidate.experience_years:g} yrs")
    profile_cols[2].metric("Skills", str(len(candidate.skills)))
    profile_cols[3].metric("Projects", str(len(candidate.projects)))

    if candidate.skills:
        st.markdown("**Detected skills**")
        st.markdown(_chips(candidate.skills[:18]), unsafe_allow_html=True)

    if candidate.experiences:
        st.markdown("**Experience**")
        for experience in candidate.experiences[:4]:
            title = " - ".join(part for part in [experience.title, experience.company] if part)
            st.write(title or "Experience entry")
            if experience.description:
                st.caption(experience.description[:240])

    if candidate.projects:
        st.markdown("**Projects**")
        for project in candidate.projects[:4]:
            st.write(project.name)
            if project.description:
                st.caption(project.description[:240])


def _get_jd_text(jd_text: str, jd_file) -> str:
    parts = [jd_text or ""]
    if jd_file:
        parts.append(extract_jd_text(jd_file.name, jd_file.getvalue()))
    return "\n\n".join(part for part in parts if part)


def _parse_linkedin_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        url = line.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _sorted_results(results: list[ScoringResult]) -> list[ScoringResult]:
    return sorted(results, key=lambda result: result.weighted_total, reverse=True)


def _eta(start_time: float, completed: int, total: int) -> str:
    if completed <= 0:
        return "calculating..."
    elapsed = time.time() - start_time
    remaining = max(total - completed, 0)
    seconds = int((elapsed / completed) * remaining)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds}s"


def _recommendation_icon(recommendation: Recommendation) -> str:
    if recommendation == Recommendation.HIRE:
        return "[HIRE]"
    if recommendation == Recommendation.MAYBE:
        return "[MAYBE]"
    return "[NO HIRE]"


def _metric_card(label: str, value: str) -> str:
    return (
        '<div class="metric-card">'
        f'<div class="metric-label">{_escape(label)}</div>'
        f'<div class="metric-value">{_escape(value)}</div>'
        "</div>"
    )


def _mini_stat(label: str, value: str) -> str:
    return (
        '<div class="mini-stat">'
        f'<div class="metric-label">{_escape(label)}</div>'
        f'<div class="metric-value" style="font-size: 1rem;">{_escape(value)}</div>'
        "</div>"
    )


def _candidate_card(result: ScoringResult) -> str:
    badge_class = _recommendation_badge_class(result.recommendation)
    source = result.source.value.title() if result.source else "-"
    score_cells = []
    for dimension in ScoringResult.WEIGHTS:
        score_item = getattr(result.scores, dimension)
        score_cells.append(
            f"""
            <div class="score-cell">
                <div class="score-title">{_escape(DIMENSION_LABELS[dimension])}</div>
                <div class="score-number">{score_item.score:.1f}</div>
                {_score_bar(score_item.score)}
            </div>
            """
        )

    return f"""
    <div class="result-card">
        <div class="result-head">
            <div>
                <p class="candidate-name">{_escape(result.candidate_name)}</p>
                <div class="candidate-meta">Source: {_escape(source)} | Semantic similarity: {result.semantic_similarity:.2f}/10</div>
            </div>
            <div style="text-align: right;">
                <div class="badge {badge_class}">{_escape(result.recommendation.value)}</div>
                <div class="score-number" style="margin-top: 0.35rem;">{result.weighted_total:.2f}/10</div>
            </div>
        </div>
        <div class="summary-box">{_escape(result.summary)}</div>
        <div class="score-grid">{''.join(score_cells)}</div>
    </div>
    """


def _score_bar(score: float) -> str:
    width = max(0, min(100, score * 10))
    return (
        '<div class="bar-track">'
        f'<div class="bar-fill" style="width: {width:.0f}%; background: {_score_color(score)};"></div>'
        "</div>"
    )


def _score_color(score: float) -> str:
    if score >= 7:
        return "#16a34a"
    if score >= 4:
        return "#eab308"
    return "#dc2626"


def _recommendation_badge_class(recommendation: Recommendation) -> str:
    if recommendation == Recommendation.HIRE:
        return "badge-hire"
    if recommendation == Recommendation.MAYBE:
        return "badge-maybe"
    return "badge-no-hire"


def _chips(values: list[str]) -> str:
    if not values:
        return '<div class="chip-row"><span class="chip">No skills extracted yet</span></div>'
    chips = "".join(f'<span class="chip">{_escape(value)}</span>' for value in values)
    return f'<div class="chip-row">{chips}</div>'


def _find_candidate(name: str) -> CandidateProfile | None:
    for candidate in st.session_state.candidates:
        if candidate.name == name:
            return candidate
    return None


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
