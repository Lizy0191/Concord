"""Regenerate the original two-page PDF fixture (authoring-only: ReportLab 4.x).

The checked-in PDF is used directly by tests; ReportLab is not a runtime dependency.
Run on an authoring host with `uv run --with reportlab python scripts/generate_document_fixture.py`.
"""

from pathlib import Path


def main() -> None:
    from reportlab.pdfgen.canvas import Canvas

    path = Path(__file__).resolve().parents[1] / "fixtures/coordination-notice.pdf"
    canvas = Canvas(str(path), pagesize=(420, 420), invariant=1, pageCompression=0)
    canvas.setTitle("Synthetic coordination notice - parser verification fixture")
    pages = [
        (
            "Revision notice",
            "Drawing V17 / WP-200",
            [
                "Duct route E-01 changes at Level 02 East.",
                "The previous accepted drawing was V16.",
                "Record acknowledgement before installation.",
                "Source marker: PDF-PAGE-ONE-V17.",
            ],
        ),
        (
            "Inspection record",
            "QC-SECOND-PAGE / WP-300",
            [
                "The cable tray inspection is awaiting review.",
                "Crew availability is not an inspection approval.",
                "A human safety approver must verify the record.",
                "Source marker: PDF-PAGE-TWO-QC.",
            ],
        ),
    ]
    for index, (title, subtitle, lines) in enumerate(pages, 1):
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, 382, "CONSTRUCTION COORDINATION / SYNTHETIC TEST DATA")
        canvas.setFont("Helvetica-Bold", 22)
        canvas.drawString(36, 336, title)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(36, 306, subtitle)
        canvas.setLineWidth(0.5)
        canvas.line(36, 286, 384, 286)
        canvas.setFont("Helvetica", 11)
        for line, y in zip(lines, (256, 230, 204, 164), strict=True):
            canvas.drawString(36, y, line)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, 60, "Not construction instructions or safety authorization.")
        canvas.drawString(36, 42, f"Parser fixture / physical page {index} of 2")
        canvas.showPage()
    canvas.save()
    print(path)


if __name__ == "__main__":
    main()
