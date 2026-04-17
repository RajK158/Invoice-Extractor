"""
data/samples/generate_samples.py - Generate synthetic sample invoice images for testing.

Produces a small set of realistic invoice images covering multiple languages,
currencies, and formats — ready to use as demo data.

Usage:
    python data/samples/generate_samples.py --count 10 --output data/samples/
"""

import argparse
import io
import random
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow required: pip install Pillow")
    sys.exit(1)

# ─── Sample Data ─────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "lang": "en",
        "currency": "USD",
        "vendor": "Acme Technologies LLC",
        "buyer": "Global Imports Inc",
        "tax_label": "Tax (18%)",
        "total_label": "Total Amount Due",
        "subtotal_label": "Subtotal",
        "date_fmt": "March 15, 2024",
    },
    {
        "lang": "en",
        "currency": "GBP",
        "vendor": "BrightStar Solutions Ltd",
        "buyer": "Northern Supplies PLC",
        "tax_label": "VAT (20%)",
        "total_label": "Grand Total",
        "subtotal_label": "Net Amount",
        "date_fmt": "15/03/2024",
    },
    {
        "lang": "hi",
        "currency": "INR",
        "vendor": "राज एंटरप्राइजेज",
        "buyer": "मुंबई ट्रेडर्स",
        "tax_label": "GST (18%)",
        "total_label": "कुल राशि",
        "subtotal_label": "उप-योग",
        "date_fmt": "15-03-2024",
    },
    {
        "lang": "de",
        "currency": "EUR",
        "vendor": "TechPro GmbH",
        "buyer": "Müller Handel AG",
        "tax_label": "MwSt. (19%)",
        "total_label": "Gesamtbetrag",
        "subtotal_label": "Zwischensumme",
        "date_fmt": "15.03.2024",
    },
    {
        "lang": "fr",
        "currency": "EUR",
        "vendor": "Solutions Numériques SARL",
        "buyer": "Commerce Atlantique",
        "tax_label": "TVA (20%)",
        "total_label": "Montant Total",
        "subtotal_label": "Sous-total",
        "date_fmt": "15/03/2024",
    },
    {
        "lang": "ar",
        "currency": "AED",
        "vendor": "الفاروق للتجارة",
        "buyer": "شركة النور",
        "tax_label": "ضريبة القيمة المضافة (5%)",
        "total_label": "المجموع الكلي",
        "subtotal_label": "المجموع الفرعي",
        "date_fmt": "2024/03/15",
    },
    {
        "lang": "es",
        "currency": "USD",
        "vendor": "Soluciones Tecnológicas S.A.",
        "buyer": "Importaciones del Norte",
        "tax_label": "IVA (16%)",
        "total_label": "Total a Pagar",
        "subtotal_label": "Subtotal",
        "date_fmt": "15/03/2024",
    },
]

CURRENCY_SYMBOLS = {
    "USD": "$", "GBP": "£", "EUR": "€", "INR": "₹",
    "AED": "AED ", "JPY": "¥",
}

LINE_ITEMS = [
    ("Software License", 800, 1),
    ("Consulting Services", 1200, 2),
    ("Hardware Components", 450, 3),
    ("Annual Maintenance", 600, 1),
    ("Training Sessions", 350, 5),
    ("Cloud Hosting", 200, 12),
]


def draw_invoice(template: dict, inv_num: str) -> Image.Image:
    """Render a synthetic invoice image for the given template."""
    width, height = 1200, 1800
    bg = (255, 255, 255)
    fg = (20, 20, 20)
    accent = (30, 80, 160)
    light = (240, 245, 255)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    sym = CURRENCY_SYMBOLS.get(template["currency"], "")
    items = random.sample(LINE_ITEMS, k=random.randint(2, 4))
    subtotal = sum(item[1] * item[2] for item in items)
    tax_rate = random.choice([0.05, 0.1, 0.15, 0.18, 0.19, 0.20])
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)

    # Header band
    draw.rectangle([0, 0, width, 120], fill=accent)
    draw.text((50, 35), "INVOICE", fill=(255, 255, 255))
    draw.text((800, 35), template["vendor"], fill=(200, 220, 255))

    y = 150

    # Invoice metadata
    draw.text((50, y), f"Invoice No:     {inv_num}", fill=fg)
    y += 45
    draw.text((50, y), f"Invoice Date:   {template['date_fmt']}", fill=fg)
    y += 45
    draw.text((50, y), f"Due Date:       30/04/2024", fill=fg)
    y += 45
    draw.text((50, y), f"Currency:       {template['currency']}", fill=fg)
    y += 60

    # Separator
    draw.rectangle([50, y, width - 50, y + 2], fill=accent)
    y += 20

    # Parties
    draw.text((50, y), f"From:  {template['vendor']}", fill=fg)
    draw.text((600, y), f"Bill To:  {template['buyer']}", fill=fg)
    y += 45
    draw.text((50, y), "123 Business Park, Suite 100", fill=(100, 100, 100))
    draw.text((600, y), "456 Commerce Street, Floor 2", fill=(100, 100, 100))
    y += 80

    # Tax ID (GSTIN format for INR, VAT number for EUR)
    if template["currency"] == "INR":
        draw.text((50, y), "GSTIN: 27AAPFU0939F1ZV", fill=fg)
    elif template["currency"] in ("EUR", "GBP"):
        draw.text((50, y), f"VAT No: {template['lang'].upper()}123456789", fill=fg)
    y += 60

    # Line items header
    draw.rectangle([50, y, width - 50, y + 40], fill=light)
    draw.text((60, y + 10), "Description", fill=fg)
    draw.text((700, y + 10), "Qty", fill=fg)
    draw.text((800, y + 10), "Rate", fill=fg)
    draw.text((950, y + 10), "Amount", fill=fg)
    y += 50

    for desc, rate, qty in items:
        amount = rate * qty
        draw.text((60, y), desc, fill=fg)
        draw.text((700, y), str(qty), fill=fg)
        draw.text((800, y), f"{sym}{rate:,.2f}", fill=fg)
        draw.text((950, y), f"{sym}{amount:,.2f}", fill=fg)
        y += 40

    y += 30
    draw.rectangle([50, y, width - 50, y + 2], fill=(200, 200, 200))
    y += 20

    # Totals
    draw.text((700, y), f"{template['subtotal_label']}:", fill=fg)
    draw.text((950, y), f"{sym}{subtotal:,.2f}", fill=fg)
    y += 40
    draw.text((700, y), f"{template['tax_label']}:", fill=fg)
    draw.text((950, y), f"{sym}{tax:,.2f}", fill=fg)
    y += 40

    draw.rectangle([700, y, width - 50, y + 50], fill=accent)
    draw.text((720, y + 12), f"{template['total_label']}:", fill=(255, 255, 255))
    draw.text((950, y + 12), f"{sym}{total:,.2f}", fill=(255, 255, 255))
    y += 80

    # Payment terms
    draw.text((50, y), "Payment Terms:  Net 30 days", fill=fg)
    y += 45
    draw.text((50, y), "Bank: First National Bank  |  IBAN: XX00 1234 5678 9012 3456 78", fill=(100, 100, 100))

    # Footer
    draw.rectangle([0, height - 60, width, height], fill=light)
    draw.text((50, height - 40), "Thank you for your business!", fill=(80, 80, 80))

    return img


def generate_samples(count: int, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating {count} sample invoice images in {output_dir}…")

    for i in range(count):
        template = TEMPLATES[i % len(TEMPLATES)]
        inv_num = f"INV-{2024}-{i+1:04d}"
        img = draw_invoice(template, inv_num)

        filename = f"sample_{template['lang']}_{template['currency']}_{i+1:03d}.png"
        img.save(output_dir / filename, "PNG", dpi=(300, 300))
        print(f"  ✓ {filename}")

    print(f"\n✅ Generated {count} sample invoices in: {output_dir}")
    print("   Use these with: Upload Invoice or Batch Process in the Streamlit app.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic invoice images")
    parser.add_argument("--count", type=int, default=10, help="Number of invoices to generate")
    parser.add_argument("--output", type=str, default="data/samples", help="Output directory")
    args = parser.parse_args()

    generate_samples(args.count, Path(args.output))
