"""
Export — Markdown / HTML / PDF
=================================
Turns a finished research turn (question, the agent's final answer, and any
virtual files it produced) into a downloadable report in three formats.

PDF library choice: `reportlab` rather than `weasyprint` or `pdfkit`.
weasyprint needs system-level Pango/Cairo libraries and pdfkit needs the
wkhtmltopdf binary — neither is guaranteed to be present on a deployment
target like Streamlit Community Cloud, and adding them via apt is an extra
moving part. reportlab is pure-Python, ships as a normal pip wheel, and is
sufficient for a structured text report like this one.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


@dataclass
class ReportData:
    """Everything needed to render a report, gathered from the Streamlit
    session for a single completed research turn."""

    query: str
    answer: str
    model: str
    created_at: datetime
    sources: list[str]
    files: dict[str, str]  # virtual file path -> content


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def to_markdown(report: ReportData) -> str:
    lines = [
        f"# Research Report",
        "",
        f"**Query:** {report.query}",
        f"**Model:** {report.model}",
        f"**Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## Answer",
        "",
        report.answer,
        "",
    ]
    if report.sources:
        lines += ["## Sources", ""]
        lines += [f"{i + 1}. {url}" for i, url in enumerate(report.sources)]
        lines += [""]
    if report.files:
        lines += ["## Generated Files", ""]
        for path, content in report.files.items():
            lines += [f"### `{path}`", "", "```", content.strip(), "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def to_html(report: ReportData) -> str:
    def esc(s: str) -> str:
        return html_lib.escape(s)

    sources_html = ""
    if report.sources:
        items = "".join(f"<li><a href='{esc(u)}'>{esc(u)}</a></li>" for u in report.sources)
        sources_html = f"<h2>Sources</h2><ol>{items}</ol>"

    files_html = ""
    if report.files:
        blocks = "".join(
            f"<h3><code>{esc(p)}</code></h3><pre>{esc(c)}</pre>"
            for p, c in report.files.items()
        )
        files_html = f"<h2>Generated Files</h2>{blocks}"

    # Answer comes from the LLM as markdown-ish text; render line breaks as
    # <br> and leave the rest as plain escaped text — good enough for a
    # downloadable report without pulling in a full markdown renderer.
    answer_html = esc(report.answer).replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Research Report — {esc(report.query[:60])}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
          max-width: 760px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
  h1 {{ font-size: 1.6rem; border-bottom: 2px solid #eee; padding-bottom: .5rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2rem; }}
  .meta {{ color: #666; font-size: .9rem; }}
  pre {{ background: #f6f8fa; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
  code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
  <h1>Research Report</h1>
  <p class="meta">
    <strong>Query:</strong> {esc(report.query)}<br>
    <strong>Model:</strong> {esc(report.model)}<br>
    <strong>Generated:</strong> {esc(report.created_at.strftime('%Y-%m-%d %H:%M UTC'))}
  </p>
  <h2>Answer</h2>
  <p>{answer_html}</p>
  {sources_html}
  {files_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _markdown_bold_to_reportlab(text: str) -> str:
    """Very small markdown->reportlab-markup pass: **bold** and escaping.
    Not a full markdown renderer — just enough so common LLM-formatted
    answers (bold key terms, simple paragraphs) look right in the PDF.
    """
    escaped = html_lib.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def to_pdf_bytes(report: ReportData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], alignment=TA_LEFT, fontSize=20
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], textColor=colors.grey, fontSize=9
    )
    h2_style = styles["Heading2"]
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=10.5, leading=15
    )

    story = [
        Paragraph("Research Report", title_style),
        Spacer(1, 6),
        Paragraph(f"<b>Query:</b> {html_lib.escape(report.query)}", meta_style),
        Paragraph(f"<b>Model:</b> {html_lib.escape(report.model)}", meta_style),
        Paragraph(
            f"<b>Generated:</b> {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
            meta_style,
        ),
        Spacer(1, 16),
        Paragraph("Answer", h2_style),
    ]

    for para in report.answer.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(_markdown_bold_to_reportlab(para), body_style))
            story.append(Spacer(1, 8))

    if report.sources:
        story.append(Paragraph("Sources", h2_style))
        items = [
            ListItem(Paragraph(html_lib.escape(url), body_style))
            for url in report.sources
        ]
        story.append(ListFlowable(items, bulletType="1"))
        story.append(Spacer(1, 8))

    if report.files:
        story.append(Paragraph("Generated Files", h2_style))
        for path, content in report.files.items():
            story.append(Paragraph(f"<font face='Courier'>{html_lib.escape(path)}</font>", body_style))
            snippet = content.strip()[:2000]
            story.append(
                Paragraph(
                    f"<font face='Courier' size=8>{html_lib.escape(snippet)}</font>",
                    body_style,
                )
            )
            story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()
