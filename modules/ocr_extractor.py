import os
import re
import pytesseract
import pandas as pd
from pdf2image import convert_from_path
from PIL import Image
from config import OCR_ENABLED, OCR_LANGUAGE


# ─── OCR Guard ────────────────────────────────────────────────────────────────

def check_ocr_enabled():
    if not OCR_ENABLED:
        raise RuntimeError("OCR is disabled in config.py. Set OCR_ENABLED = True to use it.")


# ─── Image Preprocessor ───────────────────────────────────────────────────────

def preprocess_image(img):
    """
    Convert image to grayscale to improve OCR accuracy.
    More preprocessing steps can be added here later (contrast, thresholding).
    """
    return img.convert("L")


# ─── Single Image OCR ─────────────────────────────────────────────────────────

def ocr_image(img, page_num=1):
    """
    Run OCR on a single PIL image.
    Returns a dict with page number and extracted text.
    """
    processed = preprocess_image(img)
    text = pytesseract.image_to_string(processed, lang=OCR_LANGUAGE)
    return {
        "page":  page_num,
        "text":  text.strip()
    }


# ─── PDF to Images ────────────────────────────────────────────────────────────

def pdf_to_images(pdf_path, dpi=300):
    """
    Convert each page of a PDF to a PIL image.
    Higher DPI = better OCR accuracy but slower processing.
    Returns a list of PIL images.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    images = convert_from_path(pdf_path, dpi=dpi)
    return images


# ─── Extract from Scanned PDF ─────────────────────────────────────────────────

def extract_from_pdf(pdf_path, logger):
    """
    OCR a scanned PDF page by page.
    Returns a list of dicts: {page, text}
    """
    check_ocr_enabled()
    logger.info(f"Converting PDF to images for OCR: {os.path.basename(pdf_path)}")

    images = pdf_to_images(pdf_path)
    logger.info(f"  {len(images)} page(s) converted.")

    results = []
    for i, img in enumerate(images, start=1):
        logger.info(f"  OCR processing page {i}...")
        result = ocr_image(img, page_num=i)

        if result["text"]:
            results.append(result)
            logger.info(f"  Page {i}: {len(result['text'])} characters extracted.")
        else:
            logger.warning(f"  Page {i}: no text detected.")

    return results


# ─── Extract from Image File ──────────────────────────────────────────────────

def extract_from_image(image_path, logger):
    """
    OCR a single image file (PNG, JPG, TIFF, BMP).
    Returns a list with one dict: {page, text}
    """
    check_ocr_enabled()

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    logger.info(f"OCR processing image: {os.path.basename(image_path)}")
    img    = Image.open(image_path)
    result = ocr_image(img, page_num=1)

    if result["text"]:
        logger.info(f"  {len(result['text'])} characters extracted.")
    else:
        logger.warning("  No text detected in image.")

    return [result]


# ─── Table Parser from OCR Text ───────────────────────────────────────────────

def parse_table_from_text(text, logger):
    """
    Attempt to detect and parse a table structure from raw OCR text.
    Looks for consistent whitespace-aligned columns.
    Returns a DataFrame if a table is detected, None otherwise.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if len(lines) < 2:
        return None

    # Split each line into columns by 2+ spaces
    split_lines = [re.split(r"\s{2,}", line) for line in lines]

    # Check if column counts are consistent
    col_counts = [len(row) for row in split_lines]
    most_common = max(set(col_counts), key=col_counts.count)

    # Filter rows that match the most common column count
    consistent = [row for row in split_lines if len(row) == most_common]

    if len(consistent) < 2 or most_common < 2:
        logger.info("  No consistent table structure detected in OCR text.")
        return None

    headers = consistent[0]
    rows    = consistent[1:]
    df      = pd.DataFrame(rows, columns=headers)
    logger.info(f"  Parsed table: {len(df)} row(s), {len(df.columns)} column(s).")
    return df


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def extract(filepath, logger):
    """
    Main OCR entry point.
    Detects whether input is a PDF or image and routes accordingly.
    Tries to parse table structure from OCR text.
    Returns a dict matching the same format as pdf_extractor.extract():
        - mode: 'table' or 'text'
        - data: list of DataFrames (table) or list of dicts (text)
        - page_count: number of pages/images processed
        - source: filename
    """
    check_ocr_enabled()

    ext      = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)

    # ── Route to correct extractor ──
    if ext == ".pdf":
        pages = extract_from_pdf(filepath, logger)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        pages = extract_from_image(filepath, logger)
    else:
        raise ValueError(f"Unsupported file type for OCR: {ext}")

    if not pages:
        return {
            "mode":       "text",
            "data":       [],
            "page_count": 0,
            "source":     filename
        }

    # ── Try to parse a table from the combined text ──
    full_text  = "\n".join([p["text"] for p in pages if p["text"]])
    table_df   = parse_table_from_text(full_text, logger)

    if table_df is not None:
        return {
            "mode":       "table",
            "data":       [table_df],
            "page_count": len(pages),
            "source":     filename
        }

    # ── Fallback: return raw text ──
    return {
        "mode":       "text",
        "data":       pages,
        "page_count": len(pages),
        "source":     filename
    }