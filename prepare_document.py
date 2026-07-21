"""
One-time offline step: convert a PDF into plain text the chat app can load.

Run this locally against your own PDF before running or deploying the app:

    python prepare_document.py path/to/your-report.pdf

It writes the extracted text to data/document.txt (gitignored). The app
never reads the PDF directly — it only reads that text file. This keeps the
(possibly copyrighted) source PDF off of GitHub while the code stays public.
"""

import argparse
import sys
from pathlib import Path

from pypdf import PdfReader

DEFAULT_OUTPUT = Path("data/document.txt")


def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to the source PDF")
    parser.add_argument(
        "-o", "--output", default=str(DEFAULT_OUTPUT), help=f"Output text file (default: {DEFAULT_OUTPUT})"
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        sys.exit(f"No such file: {pdf_path}")

    text = extract_text(pdf_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    chars = len(text)
    print(f"Wrote {chars:,} characters (~{chars // 4:,} tokens) to {output_path}")


if __name__ == "__main__":
    main()
