import argparse
import os
import re
import shlex
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red


@dataclass
class ProcessResult:
    processed: list[Path]
    skipped: list[Path]
    skipped_existing: list[Path] = field(default_factory=list)


def extract_attachment_number(filename):
    match = re.match(r"^\s*b(\d+(?:-\d+)?)(?=\s*(?:[-_.\s]|$))", filename, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


def parse_user_path(path_value):
    if isinstance(path_value, Path):
        return path_value.expanduser()

    raw_path = str(path_value).strip()
    parsed_path = raw_path

    if _looks_like_shell_path(raw_path):
        try:
            parts = shlex.split(raw_path)
        except ValueError:
            parts = []

        if len(parts) == 1:
            parsed_path = parts[0]

    return Path(os.path.expandvars(parsed_path)).expanduser()


def _looks_like_shell_path(raw_path):
    if not raw_path:
        return False
    if raw_path[0] in {"'", '"'}:
        return True
    return r"\ " in raw_path


def process_directory(
    input_dir,
    output_dir,
    label="Exhibit",
    overwrite="ask",
    confirm_overwrite=None,
):
    source_dir = parse_user_path(input_dir)
    target_dir = parse_user_path(output_dir)

    if not source_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {source_dir}")
    if overwrite not in {"ask", "always", "never"}:
        raise ValueError(f"Invalid overwrite mode: {overwrite}")

    target_dir.mkdir(parents=True, exist_ok=True)

    processed = []
    skipped = []
    skipped_existing = []

    for source_pdf in sorted(source_dir.iterdir()):
        if not source_pdf.is_file() or source_pdf.suffix.lower() != ".pdf":
            continue

        attachment_number = extract_attachment_number(source_pdf.name)
        if attachment_number is None:
            skipped.append(source_pdf)
            continue

        target_pdf = target_dir / source_pdf.name
        if target_pdf.exists() and not _should_overwrite(
            target_pdf, overwrite, confirm_overwrite
        ):
            skipped_existing.append(target_pdf)
            continue

        stamp_pdf(source_pdf, target_pdf, attachment_number, label=label)
        processed.append(target_pdf)

    return ProcessResult(
        processed=processed,
        skipped=skipped,
        skipped_existing=skipped_existing,
    )


def _should_overwrite(target_pdf, overwrite, confirm_overwrite):
    if overwrite == "always":
        return True
    if overwrite == "never":
        return False
    if confirm_overwrite is not None:
        return confirm_overwrite(target_pdf)
    return ask_overwrite(target_pdf)


def ask_overwrite(target_pdf):
    while True:
        answer = input(f"File already exists: {target_pdf}. Overwrite? [y/N]: ")
        normalized = answer.strip().lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"", "n", "no"}:
            return False
        print("Please answer y/yes or n/no.")


def stamp_pdf(source_pdf, target_pdf, attachment_number, label="Exhibit"):
    reader = PdfReader(source_pdf)
    if len(reader.pages) == 0:
        raise ValueError(f"PDF has no pages: {source_pdf}")

    writer = PdfWriter(clone_from=reader)
    first_page = writer.pages[0]
    first_page.merge_page(
        _create_stamp_overlay(first_page, f"{label} {attachment_number}")
    )

    with Path(target_pdf).open("wb") as output_file:
        writer.write(output_file)


def _create_stamp_overlay(page, text):
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    font_name = "Helvetica-Bold"
    font_size = 20
    margin = 36

    packet = BytesIO()
    overlay = canvas.Canvas(packet, pagesize=(width, height))
    overlay.setFillColor(red)
    overlay.setFont(font_name, font_size)
    text_width = stringWidth(text, font_name, font_size)
    overlay.drawString(width - margin - text_width, height - margin - font_size, text)
    overlay.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Write Bates numbers at the top right of the first PDF page."
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input_dir",
        help="Path to the input directory containing the PDFs.",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        help="Path to the output directory for numbered PDFs.",
    )
    parser.add_argument(
        "-t",
        "--text",
        dest="label",
        default="Exhibit",
        help='Text written before the number. Default is "Exhibit".',
    )
    overwrite_group = parser.add_mutually_exclusive_group()
    overwrite_group.add_argument(
        "--overwrite",
        dest="overwrite",
        action="store_const",
        const="always",
        default="ask",
        help="Overwrite existing output files without asking.",
    )
    overwrite_group.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_const",
        const="never",
        help="Skip existing output files without asking.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    input_dir = args.input_dir or input("Path to input directory: ").strip()
    output_dir = args.output_dir or input("Path to output directory: ").strip()

    result = process_directory(
        input_dir,
        output_dir,
        label=args.label,
        overwrite=args.overwrite,
    )

    for path in result.processed:
        print(f"Wrote: {path}")
    for path in result.skipped:
        print(f"Skipped, no Bates number found: {path}")
    for path in result.skipped_existing:
        print(f"Skipped, already exists: {path}")
    print(f"Done. Processed {len(result.processed)} PDF(s).")


if __name__ == "__main__":
    main()
