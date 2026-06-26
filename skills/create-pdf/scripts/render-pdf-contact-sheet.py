#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


def parse_args():
    parser = argparse.ArgumentParser(description="Render a PDF to images and create a contact sheet for visual QA.")
    parser.add_argument("--pdf", required=True, help="Input PDF.")
    parser.add_argument("--out-dir", required=True, help="Directory for rendered pages.")
    parser.add_argument("--contact-sheet", required=True, help="Output contact sheet image.")
    parser.add_argument("--pdftoppm", default="pdftoppm", help="Path to pdftoppm.")
    parser.add_argument("--dpi", type=int, default=110, help="Render DPI. Default: 110.")
    parser.add_argument("--columns", type=int, default=4, help="Contact sheet columns. Default: 4.")
    parser.add_argument("--thumb-width", type=int, default=384, help="Contact sheet thumb width. Default: 384.")
    parser.add_argument("--thumb-height", type=int, default=216, help="Contact sheet thumb height. Default: 216.")
    return parser.parse_args()


def main():
    args = parse_args()
    pdf = Path(args.pdf)
    out_dir = Path(args.out_dir)
    contact_sheet = Path(args.contact_sheet)
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    if not shutil.which(args.pdftoppm) and not Path(args.pdftoppm).exists():
        raise SystemExit(f"pdftoppm not found: {args.pdftoppm}")

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("page-*.jpg"):
        old.unlink()

    prefix = out_dir / "page"
    subprocess.run(
        [args.pdftoppm, "-jpeg", "-r", str(args.dpi), str(pdf), str(prefix)],
        check=True,
    )
    pages = sorted(out_dir.glob("page-*.jpg"))
    if not pages:
        raise SystemExit("No pages rendered from PDF")

    cols = args.columns
    rows = (len(pages) + cols - 1) // cols
    pad = 18
    label_h = 24
    sheet_w = cols * args.thumb_width + (cols + 1) * pad
    sheet_h = rows * (args.thumb_height + label_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#fdfbf7")
    draw = ImageDraw.Draw(sheet)

    for idx, page in enumerate(pages):
        img = Image.open(page).convert("RGB").resize((args.thumb_width, args.thumb_height), Image.LANCZOS)
        col = idx % cols
        row = idx // cols
        x = pad + col * (args.thumb_width + pad)
        y = pad + row * (args.thumb_height + label_h + pad)
        sheet.paste(img, (x, y))
        draw.text((x, y + args.thumb_height + 5), f"{idx + 1:02d}", fill="#2C3E50")

    contact_sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact_sheet, quality=92)
    print(f"Rendered {len(pages)} pages")
    print(f"Contact sheet: {contact_sheet}")


if __name__ == "__main__":
    main()
