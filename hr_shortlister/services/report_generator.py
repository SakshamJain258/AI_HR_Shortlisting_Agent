from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from hr_shortlister.core.schemas import CandidateProfile, Recommendation, ScoringResult
from hr_shortlister.core.utils import ensure_dir, mask_email, mask_phone, safe_filename, timestamp_for_file


DIMENSION_LABELS = {
    "skills_match": "Skills Match",
    "experience_relevance": "Experience Relevance",
    "education_certs": "Education & Certs",
    "project_portfolio": "Project / Portfolio",
    "communication_quality": "Communication Quality",
}


def generate_pdf_report(
    job_title: str,
    results: list[ScoringResult],
    candidates: list[CandidateProfile],
    overrides: Iterable[dict] | None = None,
    output_path: str | Path | None = None,
) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Flowable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is required to generate PDF reports.") from exc

    sorted_results = sorted(results, key=lambda item: item.weighted_total, reverse=True)
    candidate_map = {candidate.name: candidate for candidate in candidates}
    overrides = list(overrides or [])

    if output_path is None:
        reports_dir = ensure_dir(Path("data") / "reports")
        output_path = reports_dir / f"shortlist_report_{safe_filename(job_title)}_{timestamp_for_file()}.pdf"
    else:
        output_path = Path(output_path)
        ensure_dir(output_path.parent)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CenterTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=22,
            leading=28,
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=15,
            leading=18,
            spaceBefore=8,
            spaceAfter=8,
        )
    )
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))

    class ScoreBar(Flowable):
        def __init__(self, score: float, width: float = 180, height: float = 10):
            super().__init__()
            self.score = score
            self.width = width
            self.height = height

        def draw(self):
            self.canv.setFillColor(colors.HexColor("#E5E7EB"))
            self.canv.roundRect(0, 0, self.width, self.height, 2, fill=1, stroke=0)
            self.canv.setFillColor(_score_color(self.score))
            self.canv.roundRect(0, 0, self.width * (self.score / 10), self.height, 2, fill=1, stroke=0)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    story: list = []

    shortlisted = sum(1 for result in sorted_results if result.recommendation == Recommendation.HIRE)
    story.extend(
        [
            Spacer(1, 1.2 * inch),
            Paragraph("HR Resume & LinkedIn Shortlisting Report", styles["CenterTitle"]),
            Paragraph(f"<b>Job Title:</b> {job_title}", styles["Heading2"]),
            Paragraph(f"<b>Date generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["BodyText"]),
            Paragraph(f"<b>Total candidates evaluated:</b> {len(sorted_results)}", styles["BodyText"]),
            Paragraph(f"<b>Total shortlisted:</b> {shortlisted}", styles["BodyText"]),
            PageBreak(),
        ]
    )

    story.append(Paragraph("Executive Summary", styles["SectionTitle"]))
    summary_rows = [["Rank", "Name", "Source", "Total Score", "Recommendation"]]
    for index, result in enumerate(sorted_results, start=1):
        summary_rows.append(
            [
                str(index),
                result.candidate_name,
                (result.source.value if result.source else "-").title(),
                f"{result.weighted_total:.2f}",
                result.recommendation.value,
            ]
        )
    summary_table = Table(summary_rows, colWidths=[0.55 * inch, 2.35 * inch, 1.1 * inch, 1.2 * inch, 1.45 * inch])
    summary_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]
    for row_index, result in enumerate(sorted_results, start=1):
        summary_style.append(("BACKGROUND", (4, row_index), (4, row_index), _recommendation_color(result.recommendation)))
    summary_table.setStyle(TableStyle(summary_style))
    story.extend([summary_table, PageBreak()])

    for result_index, result in enumerate(sorted_results):
        candidate = candidate_map.get(result.candidate_name)
        story.append(Paragraph(result.candidate_name, styles["Title"]))
        meta = _candidate_meta(candidate, result)
        story.append(Paragraph(meta, styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(f"<b>Summary:</b> {result.summary}", styles["BodyText"]))
        story.append(Spacer(1, 0.12 * inch))
        story.append(
            Paragraph(
                f"<b>Semantic similarity:</b> {result.semantic_similarity:.2f}/10 &nbsp;&nbsp; "
                f"<b>Weighted total:</b> {result.weighted_total:.2f}/10 &nbsp;&nbsp; "
                f"<b>Recommendation:</b> {result.recommendation.value}",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 0.2 * inch))

        chart_rows = [[Paragraph("<b>Dimension</b>", styles["Small"]), Paragraph("<b>Score</b>", styles["Small"]), ""]]
        for dimension, weight in ScoringResult.WEIGHTS.items():
            dimension_score = getattr(result.scores, dimension)
            chart_rows.append(
                [
                    DIMENSION_LABELS[dimension],
                    f"{dimension_score.score:.1f}",
                    ScoreBar(dimension_score.score),
                ]
            )
        chart_table = Table(chart_rows, colWidths=[2.2 * inch, 0.65 * inch, 2.6 * inch])
        chart_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(chart_table)
        story.append(Spacer(1, 0.18 * inch))

        dimension_rows = [["Dimension", "Score", "Weight", "Weighted", "Justification"]]
        for dimension, weight in ScoringResult.WEIGHTS.items():
            dimension_score = getattr(result.scores, dimension)
            dimension_rows.append(
                [
                    DIMENSION_LABELS[dimension],
                    f"{dimension_score.score:.1f}",
                    f"{int(weight * 100)}%",
                    f"{dimension_score.score * weight:.2f}",
                    Paragraph(dimension_score.justification, styles["Small"]),
                ]
            )
        dimension_table = Table(
            dimension_rows,
            colWidths=[1.35 * inch, 0.55 * inch, 0.6 * inch, 0.65 * inch, 3.1 * inch],
        )
        dimension_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(dimension_table)

        candidate_overrides = [entry for entry in overrides if entry.get("candidate") == result.candidate_name]
        if candidate_overrides:
            story.append(Spacer(1, 0.18 * inch))
            story.append(Paragraph("HR Override", styles["SectionTitle"]))
            for entry in candidate_overrides:
                story.append(
                    Paragraph(
                        f"{entry.get('dimension')}: {entry.get('original_score')} -> "
                        f"{entry.get('new_score')} | {entry.get('reason')}",
                        styles["Small"],
                    )
                )

        if result_index < len(sorted_results) - 1:
            story.append(PageBreak())

    doc.build(story)
    return Path(output_path)


def _candidate_meta(candidate: CandidateProfile | None, result: ScoringResult) -> str:
    source = result.source.value.title() if result.source else "-"
    if not candidate:
        return f"<b>Source:</b> {source}"

    parts = [
        f"<b>Source:</b> {source}",
        f"<b>Email:</b> {mask_email(candidate.email) or '-'}",
        f"<b>Phone:</b> {mask_phone(candidate.phone) or '-'}",
        f"<b>Location:</b> {candidate.location or '-'}",
    ]
    return " &nbsp;&nbsp; ".join(parts)


def _score_color(score: float):
    from reportlab.lib import colors

    if score >= 7:
        return colors.HexColor("#16A34A")
    if score >= 4:
        return colors.HexColor("#EAB308")
    return colors.HexColor("#DC2626")


def _recommendation_color(recommendation: Recommendation):
    from reportlab.lib import colors

    if recommendation == Recommendation.HIRE:
        return colors.HexColor("#BBF7D0")
    if recommendation == Recommendation.MAYBE:
        return colors.HexColor("#FEF08A")
    return colors.HexColor("#FECACA")
