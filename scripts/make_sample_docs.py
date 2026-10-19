"""Builds the fictional bakery's pricing.docx and opening-hours.pdf.

The demo ships with these files already built. Run this only if you want to
change their text:  python scripts/make_sample_docs.py
Needs python-docx and reportlab (pip install reportlab).
"""

from pathlib import Path

import docx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "sample_docs"
NOTICE = "FICTIONAL SAMPLE DATA. Little Crumb Bakery is not a real business; this file exists only for the chatbot demo."

PRICES = {
    "Breads": [
        ("Classic sourdough loaf (800 g)", "₹220"),
        ("Vegan sourdough loaf (800 g)", "₹240"),
        ("Multigrain sandwich bread", "₹120"),
        ("Brioche buns (pack of 4)", "₹160"),
    ],
    "Pastries": [
        ("Butter croissant", "₹110"),
        ("Almond croissant", "₹150"),
        ("Cinnamon roll", "₹130"),
        ("Chocolate chip cookie", "₹60"),
    ],
    "Cakes": [
        ("Chocolate truffle cake, 500 g", "₹650"),
        ("Chocolate truffle cake, 1 kg", "₹1,200"),
        ("Red velvet cake, 1 kg", "₹1,350"),
        ("Custom designer cakes", "from ₹1,800 per kg"),
    ],
    "Drinks": [
        ("Filter coffee", "₹70"),
        ("Cappuccino", "₹150"),
        ("Masala chai", "₹60"),
    ],
}


def make_docx() -> None:
    document = docx.Document()
    document.add_heading("Little Crumb Bakery: Price list (2026)", level=1)
    document.add_paragraph(NOTICE)
    for section, items in PRICES.items():
        document.add_heading(f"{section} prices", level=2)
        for item, price in items:
            document.add_paragraph(f"{item}: {price}")
    document.add_heading("Taxes and discounts", level=2)
    document.add_paragraph("All prices include GST. Students get 10% off pastries and drinks on weekdays with a valid ID.")
    document.save(OUT / "pricing.docx")


def make_pdf() -> None:
    styles = getSampleStyleSheet()
    # Built-in PDF fonts can't draw the rupee sign, so the PDF avoids it.
    story = [
        Paragraph("Little Crumb Bakery: Opening hours and location", styles["Title"]),
        Paragraph(NOTICE, styles["Italic"]),
        Spacer(1, 12),
        Paragraph("Opening hours", styles["Heading2"]),
        Paragraph("Monday to Friday: we open at 7:30 am and close at 8:00 pm.", styles["BodyText"]),
        Paragraph("Saturday: we open at 7:00 am and close at 9:00 pm.", styles["BodyText"]),
        Paragraph("Sunday: we open at 8:00 am and close at 2:00 pm. The bakery is closed on Sunday afternoons.", styles["BodyText"]),
        Paragraph("Fresh bread comes out of the oven at 7:30 am and again at 4:00 pm every day we are open.", styles["BodyText"]),
        PageBreak(),
        Paragraph("Holidays", styles["Heading2"]),
        Paragraph("We are closed on 26 January, 15 August, 2 October and on Diwali day. On Christmas Eve we stay open until 10:00 pm.", styles["BodyText"]),
        Paragraph("Address and contact", styles["Heading2"]),
        Paragraph("Little Crumb Bakery, 12 5th Cross Road, Example Nagar, Bengaluru 560000 (a made-up address).", styles["BodyText"]),
        Paragraph("Phone: +91 00000 00000 (placeholder). Email: hello@littlecrumb.example", styles["BodyText"]),
    ]
    SimpleDocTemplate(str(OUT / "opening-hours.pdf"), pagesize=A4, title="Little Crumb Bakery opening hours").build(story)


if __name__ == "__main__":
    make_docx()
    make_pdf()
    print("Wrote", OUT / "pricing.docx", "and", OUT / "opening-hours.pdf")
