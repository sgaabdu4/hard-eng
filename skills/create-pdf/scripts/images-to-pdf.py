#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def parse_args():
    parser = argparse.ArgumentParser(description="Assemble slide/page images into a 16:9 image-based PDF.")
    parser.add_argument("--input-dir", required=True, help="Directory containing slide-*.jpg/png/webp images.")
    parser.add_argument("--out", required=True, help="Output PDF path.")
    parser.add_argument("--page-width-pt", type=float, default=1152, help="PDF page width in points. Default: 16in.")
    parser.add_argument("--page-height-pt", type=float, default=648, help="PDF page height in points. Default: 9in.")
    parser.add_argument("--links-json", help="Optional JSON file of page link rectangles from export-html-deck.mjs.")
    return parser.parse_args()


def load_links(path):
    if not path:
        return {"sourceWidth": 1280, "sourceHeight": 720, "pages": []}
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def add_page_links(pdf, page_links, source_width, source_height, page_width_pt, page_height_pt):
    scale_x = page_width_pt / source_width
    scale_y = page_height_pt / source_height
    for link in page_links:
        rect = link.get("rect") or {}
        href = link.get("href")
        if not href:
            continue
        x1 = float(rect.get("x", 0)) * scale_x
        y_top = float(rect.get("y", 0)) * scale_y
        x2 = x1 + float(rect.get("width", 0)) * scale_x
        y2_from_top = y_top + float(rect.get("height", 0)) * scale_y
        y1 = page_height_pt - y2_from_top
        y2 = page_height_pt - y_top
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        pdf.linkURL(href, (x1, y1, x2, y2), relative=0, thickness=0)


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    out = Path(args.out)
    link_data = load_links(args.links_json)
    source_width = float(link_data.get("sourceWidth") or 1280)
    source_height = float(link_data.get("sourceHeight") or 720)
    link_pages = link_data.get("pages") or []
    paths = sorted(
        list(input_dir.glob("slide-*.jpg"))
        + list(input_dir.glob("slide-*.jpeg"))
        + list(input_dir.glob("slide-*.png"))
        + list(input_dir.glob("slide-*.webp"))
    )
    if not paths:
        raise SystemExit(f"No slide images found in {input_dir}")

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(out), pagesize=(args.page_width_pt, args.page_height_pt), pageCompression=1)
    for index, path in enumerate(paths):
        pdf.drawImage(
            ImageReader(str(path)),
            0,
            0,
            width=args.page_width_pt,
            height=args.page_height_pt,
            preserveAspectRatio=False,
            mask=None,
        )
        add_page_links(
            pdf,
            link_pages[index] if index < len(link_pages) else [],
            source_width,
            source_height,
            args.page_width_pt,
            args.page_height_pt,
        )
        pdf.showPage()
    pdf.save()
    print(f"Wrote {len(paths)} pages: {out}")


if __name__ == "__main__":
    main()
