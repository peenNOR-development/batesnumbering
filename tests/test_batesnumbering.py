import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas
from pypdf import PdfReader

from batesnumbering import extract_attachment_number, process_directory


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FilenameParsingTests(unittest.TestCase):
    def test_extracts_attachment_number_with_original_leading_zeroes(self):
        cases = {
            "b01 - contract.pdf": "01",
            "b001-invoice.pdf": "001",
            "B1 - note.pdf": "1",
            "b04-7 - sub-attachment.pdf": "04-7",
        }

        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                self.assertEqual(extract_attachment_number(filename), expected)

    def test_returns_none_when_filename_does_not_start_with_attachment_number(self):
        self.assertIsNone(extract_attachment_number("invoice b01.pdf"))


class PdfStampingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).parent / "tmp"
        self.input_dir = self.tmp / "input"
        self.output_dir = self.tmp / "output"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.input_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_process_directory_stamps_matching_pdfs_on_first_page_only(self):
        source_pdf = self.input_dir / "b001 - agreement.pdf"
        skipped_pdf = self.input_dir / "note.pdf"
        self._create_two_page_pdf(source_pdf)
        self._create_two_page_pdf(skipped_pdf)

        result = process_directory(self.input_dir, self.output_dir)

        stamped_pdf = self.output_dir / "b001 - agreement.pdf"
        self.assertEqual(result.processed, [stamped_pdf])
        self.assertEqual(result.skipped, [skipped_pdf])
        self.assertTrue(stamped_pdf.exists())
        self.assertFalse((self.output_dir / "note.pdf").exists())

        reader = PdfReader(stamped_pdf)
        self.assertIn("Exhibit 001", reader.pages[0].extract_text())
        self.assertNotIn("Exhibit 001", reader.pages[1].extract_text())

    def test_process_directory_can_write_back_to_same_folder(self):
        source_pdf = self.input_dir / "b01 - agreement.pdf"
        self._create_two_page_pdf(source_pdf)

        result = process_directory(self.input_dir, self.input_dir, overwrite="always")

        self.assertEqual(result.processed, [source_pdf])
        reader = PdfReader(source_pdf)
        self.assertIn("Exhibit 01", reader.pages[0].extract_text())
        self.assertIn("Second page", reader.pages[1].extract_text())

    def test_process_directory_accepts_shell_escaped_prompt_paths(self):
        input_dir = self.tmp / "A - WORK" / "Input"
        output_dir = self.tmp / "A - WORK" / "Output"
        input_dir.mkdir(parents=True)
        source_pdf = input_dir / "b01 - agreement.pdf"
        self._create_two_page_pdf(source_pdf)

        escaped_input = str(input_dir).replace(" ", r"\ ")
        escaped_output = str(output_dir).replace(" ", r"\ ")

        result = process_directory(escaped_input, escaped_output)

        stamped_pdf = output_dir / "b01 - agreement.pdf"
        self.assertEqual(result.processed, [stamped_pdf])
        reader = PdfReader(stamped_pdf)
        self.assertIn("Exhibit 01", reader.pages[0].extract_text())

    def test_process_directory_stamps_sub_numbered_attachment(self):
        source_pdf = self.input_dir / "b04-7 - sub-attachment.pdf"
        self._create_two_page_pdf(source_pdf)

        result = process_directory(self.input_dir, self.output_dir)

        stamped_pdf = self.output_dir / "b04-7 - sub-attachment.pdf"
        self.assertEqual(result.processed, [stamped_pdf])
        reader = PdfReader(stamped_pdf)
        self.assertIn("Exhibit 04-7", reader.pages[0].extract_text())

    def test_process_directory_uses_custom_label_text(self):
        source_pdf = self.input_dir / "b04-7 - sub-attachment.pdf"
        self._create_two_page_pdf(source_pdf)

        process_directory(self.input_dir, self.output_dir, label="Attachment")

        stamped_pdf = self.output_dir / "b04-7 - sub-attachment.pdf"
        reader = PdfReader(stamped_pdf)
        self.assertIn("Attachment 04-7", reader.pages[0].extract_text())
        self.assertNotIn("Exhibit 04-7", reader.pages[0].extract_text())

    def test_process_directory_asks_before_overwriting_existing_output(self):
        source_pdf = self.input_dir / "b01 - agreement.pdf"
        existing_pdf = self.output_dir / "b01 - agreement.pdf"
        self._create_two_page_pdf(source_pdf)
        self._create_two_page_pdf(existing_pdf, first_text="Existing output")

        asked_paths = []

        def decline_overwrite(path):
            asked_paths.append(path)
            return False

        result = process_directory(
            self.input_dir,
            self.output_dir,
            confirm_overwrite=decline_overwrite,
        )

        self.assertEqual(asked_paths, [existing_pdf])
        self.assertEqual(result.processed, [])
        self.assertEqual(result.skipped_existing, [existing_pdf])
        reader = PdfReader(existing_pdf)
        self.assertIn("Existing output", reader.pages[0].extract_text())
        self.assertNotIn("Exhibit 01", reader.pages[0].extract_text())

    def test_process_directory_can_overwrite_existing_output(self):
        source_pdf = self.input_dir / "b01 - agreement.pdf"
        existing_pdf = self.output_dir / "b01 - agreement.pdf"
        self._create_two_page_pdf(source_pdf)
        self._create_two_page_pdf(existing_pdf, first_text="Existing output")

        result = process_directory(self.input_dir, self.output_dir, overwrite="always")

        self.assertEqual(result.processed, [existing_pdf])
        reader = PdfReader(existing_pdf)
        self.assertIn("Exhibit 01", reader.pages[0].extract_text())
        self.assertNotIn("Existing output", reader.pages[0].extract_text())

    @staticmethod
    def _create_two_page_pdf(path, first_text="First page", second_text="Second page"):
        pdf = canvas.Canvas(str(path), pagesize=(300, 400))
        pdf.drawString(40, 300, first_text)
        pdf.showPage()
        pdf.drawString(40, 300, second_text)
        pdf.save()


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).parent / "tmp-cli"
        self.input_dir = self.tmp / "input"
        self.output_dir = self.tmp / "output"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.input_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_command_line_arguments_run_without_prompts(self):
        source_pdf = self.input_dir / "b01 - agreement.pdf"
        PdfStampingTests._create_two_page_pdf(source_pdf)

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "batesnumbering.py"),
                "-i",
                str(self.input_dir),
                "-o",
                str(self.output_dir),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("Path to input", completed.stdout)
        self.assertTrue((self.output_dir / "b01 - agreement.pdf").exists())

    def test_command_line_can_force_overwrite_and_set_label_text(self):
        source_pdf = self.input_dir / "b01 - agreement.pdf"
        existing_pdf = self.output_dir / "b01 - agreement.pdf"
        self.output_dir.mkdir(parents=True)
        PdfStampingTests._create_two_page_pdf(source_pdf)
        PdfStampingTests._create_two_page_pdf(existing_pdf, first_text="Existing output")

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "batesnumbering.py"),
                "-i",
                str(self.input_dir),
                "-o",
                str(self.output_dir),
                "--overwrite",
                "-t",
                "Attachment",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("Overwrite", completed.stdout)
        reader = PdfReader(existing_pdf)
        self.assertIn("Attachment 01", reader.pages[0].extract_text())
        self.assertNotIn("Existing output", reader.pages[0].extract_text())

    def test_command_line_default_prompts_before_existing_output(self):
        source_pdf = self.input_dir / "b01 - agreement.pdf"
        existing_pdf = self.output_dir / "b01 - agreement.pdf"
        self.output_dir.mkdir(parents=True)
        PdfStampingTests._create_two_page_pdf(source_pdf)
        PdfStampingTests._create_two_page_pdf(existing_pdf, first_text="Existing output")

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "batesnumbering.py"),
                "-i",
                str(self.input_dir),
                "-o",
                str(self.output_dir),
            ],
            input="n\n",
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Overwrite", completed.stdout)
        reader = PdfReader(existing_pdf)
        self.assertIn("Existing output", reader.pages[0].extract_text())
        self.assertNotIn("Exhibit 01", reader.pages[0].extract_text())


if __name__ == "__main__":
    unittest.main()
