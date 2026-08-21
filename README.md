# Bates Numbering

Python tool for stamping Bates numbers on PDF files. It reads PDF filenames that
start with a Bates number, for example `b01 - contract.pdf`,
`b001-invoice.pdf`, `b1 - note.pdf`, or `b04-7 - sub-attachment.pdf`, and writes
`Exhibit <number>` in red, bold, 20 pt text at the top right of the first page.

## Setup

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run interactively:

```bash
python3 batesnumbering.py
```

Run with command line parameters:

```bash
python3 batesnumbering.py -i "/path/to/input" -o "/path/to/output"
```

Use custom label text:

```bash
python3 batesnumbering.py -i "/path/to/input" -o "/path/to/output" -t "Attachment"
```

By default, the program asks before overwriting each output file that already
exists. Use `--overwrite` to overwrite existing output files without asking:

```bash
python3 batesnumbering.py -i "/path/to/input" -o "/path/to/output" --overwrite
```

Use `--no-overwrite` to skip existing output files without asking:

```bash
python3 batesnumbering.py -i "/path/to/input" -o "/path/to/output" --no-overwrite
```

If `-i` or `-o` is missing, the program asks for the missing path. Files that do
not start with a Bates number are skipped.

You can paste paths with spaces as plain paths, quoted paths, or shell-escaped
paths, for example:

```text
/Users/name/A - WORK/Case/Input
/Users/name/A\ -\ WORK/Case/Input
"/Users/name/A - WORK/Case/Input"
```

Use `-t "Bilag"` if you need the old Norwegian stamp text.
