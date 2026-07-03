# Data Extractor

A powerful command-line tool for extracting structured data from PDFs, Word documents,
spreadsheets, images, and websites. Built for freelance data entry and extraction jobs —
handles the most common client requests out of the box.

---

## What It Does

- Extracts tables and text from PDFs (including scanned/image PDFs via OCR)
- Extracts tables and paragraphs from Word documents (.docx)
- Cleans and restructures messy Excel and CSV files
- Scrapes tables, links, and contact info from websites
- Runs OCR on image files (PNG, JPG, TIFF, BMP)
- Outputs to CSV, JSON, and/or Excel in one command
- Processes entire folders of files in a single batch job
- Generates a detailed log file for every job

---

## Project Structure

data-extractor/
│
├── main.py                  # Entry point — handles all routing
├── config.py                # Settings, paths, modes
├── README.md
│
├── modules/
│   ├── pdf_extractor.py     # PDF table and text extraction
│   ├── ocr_extractor.py     # OCR for scanned PDFs and images
│   ├── web_scraper.py       # Website scraping
│   ├── doc_extractor.py     # Word document extraction
│   └── excel_cleaner.py     # Excel and CSV cleaning
│
│
├── modes/
│   ├── invoice_mode.py      # Invoice field mapping and cleaning
│   ├── resume_mode.py       # Resume/CV field mapping and cleaning
│   ├── contact_mode.py      # Contact list field mapping and cleaning
│   └── catalog_mode.py      # Product catalog field mapping and cleaning
│
├── output/                  # All generated output files land here
└── logs/                    # Job log files land here

---

## Installation

**Python 3.8+ required.**

Install Python dependencies:

```bash
pip install pdfplumber pandas openpyxl pytesseract pdf2image pillow requests beautifulsoup4 python-docx fpdf2
```

Install system dependencies (required for OCR):

```bash
sudo apt install tesseract-ocr poppler-utils
```

---

## Usage

### Basic Syntax

```bash
python3 main.py <input> [--mode MODE] [--format FORMAT] [--batch]
```

### Arguments

| Argument | Description | Default |
|---|---|---|
| `input` | File path, folder path, URL, or .txt file of URLs | required |
| `--mode` | Job mode: `general`, `invoice`, `resume`, `contact`, `catalog` | `general` |
| `--format` | Output format(s): `csv`, `json`, `xlsx` | `csv` |
| `--batch` | Process all files in a folder | off |

---

## Examples

### Single PDF — General Extraction
```bash
python3 main.py report.pdf --format csv
```

### Invoice PDF — Invoice Mode
```bash
python3 main.py invoice.pdf --mode invoice --format csv xlsx
```

### Resume PDF — Resume Mode
```bash
python3 main.py resume.pdf --mode resume --format csv
```

### Contact List PDF — Contact Mode
```bash
python3 main.py contacts.pdf --mode contact --format csv json
```

### Product Catalog PDF — Catalog Mode
```bash
python3 main.py catalog.pdf --mode catalog --format csv xlsx
```

### Word Document
```bash
python3 main.py document.docx --format csv
```

### Messy Excel File — Clean and Restructure
```bash
python3 main.py messy_data.xlsx --format csv
```

### CSV File — Clean and Convert
```bash
python3 main.py data.csv --format xlsx json
```

### Scanned PDF or Image — OCR
```bash
python3 main.py scanned_invoice.pdf --mode invoice --format csv
python3 main.py receipt_photo.jpg --format csv
```

### Website — Scrape Tables
```bash
python3 main.py https://example.com --format csv
```

### Text File of URLs — Batch Web Scrape
```bash
python3 main.py urls.txt --format csv
```

### Batch — Entire Folder
```bash
python3 main.py ./client_files --batch --format csv xlsx
```

### All Three Output Formats at Once
```bash
python3 main.py invoice.pdf --mode invoice --format csv json xlsx
```

---

## Example

**Input:** `test_invoice.pdf` — a scanned invoice with a line-item table

**Run:**
​```bash
python3 main.py test_invoice.pdf --mode invoice --format csv
​```

**Output:** `output/test_invoice.csv`

| page | description       | quantity | unit_price | amount |
|------|--------------------|----------|------------|--------|
| 1    | Web Development    | 1        | 1500.00    | 1500.00|
| 1    | UI Design          | 2        | 500.00     | 1000.00|
| 1    | API Integration    | 3        | 300.00     | 900.00 |
| 1    | SEO Optimization   | 1        | 250.00     | 250.00 |
| 1    | Tax (10%)          |          |            | 365.00 |
| 1    | Grand Total        |          |            | 4015.00|

**Console output:**
​```
[2026-07-03 03:30:19] INFO - Data Extractor — Job Started
[2026-07-03 03:30:19] INFO - Input  : test_invoice.pdf
[2026-07-03 03:30:19] INFO - Mode   : invoice
[2026-07-03 03:30:20] INFO - Found 1 table(s) across 1 page(s).
[2026-07-03 03:30:20] INFO - Mapped columns: {'Description': 'description', 'Quantity': 'quantity', 'Unit Price': 'unit_price', 'Amount': 'amount'}
[2026-07-03 03:30:20] INFO - Cleaned numeric column: unit_price
[2026-07-03 03:30:20] INFO - Cleaned numeric column: amount
[2026-07-03 03:30:20] INFO - Invoice processing complete. 6 row(s) returned.

══════════════════════════════════════════════════
  JOB REPORT
══════════════════════════════════════════════════
  Files processed  : 1
  Succeeded        : 1
  Failed           : 0
  Total rows       : 6
══════════════════════════════════════════════════
​```

## Job Modes

Job modes apply intelligent field mapping and cleaning on top of raw extraction.
Each mode recognizes dozens of common column name variations automatically.

### `general`
Raw extraction with no field mapping. Use when you just need the data out as-is.

### `invoice`
Designed for invoice and billing documents.

Recognized fields:
- `invoice_number`, `date`, `due_date`, `vendor`, `client`
- `description`, `quantity`, `unit_price`, `amount`, `tax`, `discount`, `total`

What it does:
- Maps common column name variations to standard field names
- Cleans currency values to floats (`$1,500.00` → `1500.0`)
- Drops empty rows
- Logs financial summary: total due, highest/lowest invoice, total tax, vendor count

### `resume`
Designed for resume and CV documents.

Recognized fields:
- `full_name`, `email`, `phone`, `location`, `title`
- `company`, `experience`, `skills`, `education`, `linkedin`, `summary`

What it does:
- Maps column name variations to standard field names
- Validates email addresses and flags invalid/missing ones
- Normalizes phone numbers to digits only
- Normalizes skills columns (handles comma, semicolon, pipe separators)
- Logs summary: candidate count, email validity breakdown, top skills, unique locations

### `contact`
Designed for contact lists and lead lists.

Recognized fields:
- `full_name`, `first_name`, `last_name`, `email`, `phone`
- `company`, `title`, `department`, `address`, `city`, `state`, `zip`, `country`
- `website`, `linkedin`, `twitter`, `notes`

What it does:
- Splits `full_name` into `first_name` and `last_name` automatically
- Validates and flags emails
- Cleans phone numbers to digits only
- Builds a `full_address` column from address parts if split across columns
- Flags duplicate contacts by email or name
- Logs summary: total contacts, email validity, duplicate count, unique companies/cities

### `catalog`
Designed for product catalogs and inventory lists.

Recognized fields:
- `product_name`, `sku`, `description`, `category`, `brand`
- `price`, `sale_price`, `currency`, `quantity`, `weight`, `dimensions`
- `color`, `material`, `rating`, `reviews`, `url`, `image_url`, `barcode`, `status`

What it does:
- Maps column name variations to standard field names
- Cleans price columns to floats
- Calculates `discount_pct` if both `price` and `sale_price` exist
- Normalizes quantity to integers
- Normalizes SKUs to uppercase and flags missing ones
- Flags duplicate products by SKU or name
- Logs summary: product count, avg/high/low price, avg discount, brands, categories, stock

---

## Supported Input Types

| Type | Extensions |
|---|---|
| PDF | `.pdf` |
| Word Document | `.docx` |
| Spreadsheet | `.xlsx`, `.xls`, `.csv` |
| Image (OCR) | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` |
| URL | `http://`, `https://` |
| URL List | `.txt` (one URL per line) |

---

## Output

All output files are saved to the `output/` folder automatically.
All log files are saved to the `logs/` folder automatically.

### Output File Naming
Output files are named after the input file:
- `invoice.pdf` → `output/invoice.csv`, `output/invoice.xlsx`
- `contacts.docx` → `output/contacts.csv`
- `example.com` → `output/example_com.csv`

### Job Report
After every job, a summary prints to the console:
══════════════════════════════════════════════════
JOB REPORT
══════════════════════════════════════════════════
Files processed  : 5
Succeeded        : 5
Failed           : 0
Total rows       : 312
══════════════════════════════════════════════════

---

## Configuration

All settings are in `config.py`:

| Setting | Description | Default |
|---|---|---|
| `OUTPUT_DIR` | Where output files are saved | `./output` |
| `LOG_DIR` | Where log files are saved | `./logs` |
| `DEFAULT_FORMAT` | Default output format | `csv` |
| `DEFAULT_MODE` | Default job mode | `general` |
| `BATCH_FILE_LIMIT` | Max files per batch job | `500` |
| `SKIP_ON_ERROR` | Skip failed files in batch instead of stopping | `True` |
| `OCR_ENABLED` | Enable/disable OCR | `True` |
| `OCR_LANGUAGE` | Tesseract language code | `eng` |
| `TEXT_FALLBACK` | Fall back to text if no tables found | `True` |

---

## Notes

- Scanned PDFs and image files require `tesseract-ocr` and `poppler-utils` to be installed
- Web scraping respects standard HTTP responses — some sites may block automated requests
- Batch jobs with `SKIP_ON_ERROR = True` will continue processing if one file fails
- All jobs generate a log file in `logs/` for review after completion
- Multiple output formats can be requested in a single command

---

## Roadmap

- [ ] Flask web interface for browser-based uploads and downloads
- [ ] AI-assisted field extraction for unstructured documents
- [ ] Playwright support for JavaScript-heavy websites
- [ ] Email ingestion — process attachments directly from inbox
- [ ] Database export — push output directly to SQLite or PostgreSQL# Data-Parser-Extractor
