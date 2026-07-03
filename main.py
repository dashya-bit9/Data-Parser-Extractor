import sys
import os
import re
import argparse
import logging
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

sys.setrecursionlimit(10000)

from config import (
    OUTPUT_FORMATS,
    DEFAULT_FORMAT,
    MODES,
    DEFAULT_MODE,
    BATCH_ENABLED,
    BATCH_FILE_LIMIT,
    SKIP_ON_ERROR,
    LOG_ENABLED,
    OUTPUT_DIR,
    get_output_path,
    get_log_path,
    SUPPORTED_EXTENSIONS
)

from modules.pdf_extractor import extract


# ─── Logging Setup ────────────────────────────────────────────────────────────

def setup_logger(filename):
    """Set up a logger that writes to both console and a log file."""
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    if LOG_ENABLED:
        log_path = get_log_path(filename)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ─── Output Saving ────────────────────────────────────────────────────────────

def save_output(df, filename, fmt, logger):
    """Save a DataFrame to the requested format."""
    path = get_output_path(filename, fmt)

    try:
        if fmt == "csv":
            df.to_csv(path, index=False)
        elif fmt == "json":
            df.to_json(path, orient="records", indent=2)
        elif fmt == "xlsx":
            df.to_excel(path, index=False)
        else:
            logger.warning(f"Unknown format '{fmt}', skipping.")
            return

        logger.info(f"Saved {fmt.upper()}: {path}")

    except Exception as e:
        logger.error(f"Failed to save {fmt.upper()}: {e}")


# ─── Mode Routing ─────────────────────────────────────────────────────────────

def apply_mode(df, mode, logger):
    """
    Route a DataFrame through the correct job mode for field mapping.
    Falls back to the raw DataFrame if the mode isn't built yet.
    """
    try:
        if mode == "invoice":
            from modes.invoice_mode import process
            return process(df, logger)
        elif mode == "resume":
            from modes.resume_mode import process
            return process(df, logger)
        elif mode == "contact":
            from modes.contact_mode import process
            return process(df, logger)
        elif mode == "catalog":
            from modes.catalog_mode import process
            return process(df, logger)
        else:
            logger.warning(f"Mode '{mode}' not recognized. Running general extraction.")
            return df

    except NotImplementedError:
        logger.warning(f"Mode '{mode}' is not fully built yet. Running general extraction.")
        return df


# ─── Single File Processing ───────────────────────────────────────────────────

def process_file(filepath, mode, formats, logger):
    """
    Process a single file or URL through extraction and optional mode.
    Returns a summary dict for the job report.
    """
    filename = os.path.basename(filepath)
    ext      = os.path.splitext(filename)[1].lower()
    summary  = {
        "file":      filename,
        "status":    "success",
        "mode":      mode,
        "rows":      0,
        "tables":    0,
        "formats":   formats,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error":     None
    }

    logger.info(f"Processing: {filename} | Mode: {mode}")

    try:
        from modules.web_scraper import is_valid_url

        # ── URL input ──
        if is_valid_url(filepath):
            from modules.web_scraper import extract as web_extract
            result   = web_extract(filepath, logger=logger)
            base     = re.sub(r"[^\w]", "_", urlparse(filepath).netloc)

            if result["data"]:
                combined         = pd.concat(result["data"], ignore_index=True)
                summary["rows"]  = len(combined)
                for fmt in formats:
                    save_output(combined, base, fmt, logger)
            else:
                logger.warning("No data extracted from URL.")

            return summary

        # ── File input ──
        if ext == ".pdf":
            result = extract(filepath)

            # OCR fallback if no text extracted
            if result["mode"] == "text" and not result["data"]:
                logger.info("No text extracted. Attempting OCR fallback...")
                from modules.ocr_extractor import extract as ocr_extract
                result = ocr_extract(filepath, logger)

        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            from modules.ocr_extractor import extract as ocr_extract
            result = ocr_extract(filepath, logger)

        elif ext == ".txt":
            from modules.web_scraper import extract as web_extract
            result = web_extract(filepath, logger=logger)

        elif ext in [".docx"]:
            from modules.doc_extractor import extract as doc_extract
            result = doc_extract(filepath, logger)

        elif ext in [".xlsx", ".xls", ".csv"]:
            from modules.excel_cleaner import extract as excel_extract
            result = excel_extract(filepath, logger)

        else:
            raise ValueError(f"Unsupported file type: {ext}")

        # ── Handle table result ──
        if result["mode"] == "table":
            tables           = result["data"]
            summary["tables"] = len(tables)
            logger.info(f"Found {len(tables)} table(s) across {result['page_count']} page(s).")

            combined         = pd.concat(tables, ignore_index=True)
            summary["rows"]  = len(combined)

            if mode != "general":
                combined = apply_mode(combined, mode, logger)

            base = os.path.splitext(filename)[0]
            for fmt in formats:
                save_output(combined, base, fmt, logger)

        # ── Handle text result ──
        elif result["mode"] == "text":
            logger.info(f"No tables found. Extracted raw text from {result['page_count']} page(s).")
            df               = pd.DataFrame(result["data"])
            summary["rows"]  = len(df)

            base = os.path.splitext(filename)[0]
            for fmt in formats:
                save_output(df, base, fmt, logger)

    except Exception as e:
        import traceback
        summary["status"] = "failed"
        summary["error"]  = str(e)
        logger.error(f"Failed to process {filename}: {e}")
        traceback.print_exc()

    return summary


# ─── Batch Processing ─────────────────────────────────────────────────────────

def process_batch(folder, mode, formats, logger):
    """
    Process every supported file in a folder.
    Returns a list of summary dicts.
    """
    supported = (
        SUPPORTED_EXTENSIONS["document"] +
        SUPPORTED_EXTENSIONS["spreadsheet"] +
        SUPPORTED_EXTENSIONS["image"]
    )

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in supported
    ]

    if not files:
        logger.warning(f"No supported files found in: {folder}")
        return []

    if len(files) > BATCH_FILE_LIMIT:
        logger.warning(f"{len(files)} files found — limit is {BATCH_FILE_LIMIT}. Truncating.")
        files = files[:BATCH_FILE_LIMIT]

    logger.info(f"Batch job started: {len(files)} file(s) found.")
    summaries = []

    for filepath in files:
        if SKIP_ON_ERROR:
            try:
                summary = process_file(filepath, mode, formats, logger)
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Skipping {filepath}: {e}")
        else:
            summary = process_file(filepath, mode, formats, logger)
            summaries.append(summary)

    return summaries


# ─── Job Report ───────────────────────────────────────────────────────────────

def print_report(summaries):
    """Print a clean summary report after a job finishes."""
    total      = len(summaries)
    succeeded  = sum(1 for s in summaries if s["status"] == "success")
    failed     = total - succeeded
    total_rows = sum(s["rows"] for s in summaries)

    print("\n" + "═" * 50)
    print("  JOB REPORT")
    print("═" * 50)
    print(f"  Files processed  : {total}")
    print(f"  Succeeded        : {succeeded}")
    print(f"  Failed           : {failed}")
    print(f"  Total rows       : {total_rows}")
    print("═" * 50)

    if failed > 0:
        print("\n  Failed files:")
        for s in summaries:
            if s["status"] == "failed":
                print(f"  ✗ {s['file']} — {s['error']}")

    print()


# ─── CLI Argument Parser ──────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Data Extractor — Extract structured data from PDFs, docs, images, and URLs.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "input",
        help="Path to a file, folder (batch), URL, or .txt file of URLs."
    )
    parser.add_argument(
        "--mode",
        choices=list(MODES.keys()),
        default=DEFAULT_MODE,
        help=(
            "Job mode to apply field mapping.\n"
            "  general  — raw extraction, no mapping (default)\n"
            "  invoice  — extract invoice fields\n"
            "  resume   — extract resume/CV fields\n"
            "  contact  — extract contact list fields\n"
            "  catalog  — extract product catalog fields\n"
        )
    )
    parser.add_argument(
        "--format",
        nargs="+",
        choices=OUTPUT_FORMATS,
        default=[DEFAULT_FORMAT],
        help="Output format(s). Example: --format csv json xlsx"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Treat input as a folder and process all supported files inside it."
    )

    return parser.parse_args()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    args   = parse_args()
    logger = setup_logger(os.path.basename(args.input))

    logger.info("═" * 40)
    logger.info("Data Extractor — Job Started")
    logger.info(f"Input  : {args.input}")
    logger.info(f"Mode   : {args.mode}")
    logger.info(f"Formats: {', '.join(args.format)}")
    logger.info("═" * 40)

    if args.batch or os.path.isdir(args.input):
        if not BATCH_ENABLED:
            logger.error("Batch processing is disabled in config.py.")
            sys.exit(1)
        summaries = process_batch(args.input, args.mode, args.format, logger)
    else:
        summary   = process_file(args.input, args.mode, args.format, logger)
        summaries = [summary]

    print_report(summaries)


if __name__ == "__main__":
    main()