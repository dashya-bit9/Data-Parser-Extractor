import pdfplumber
import pandas as pd
import os


def clean_cell(val):
    """Normalize None and whitespace in a cell."""
    if val is None:
        return ""
    return str(val).strip()


def clean_table(table):
    """Apply clean_cell to every cell in a table."""
    return [[clean_cell(cell) for cell in row] for row in table]


def extract_tables(pdf_path):
    """
    Extract all tables from a PDF.
    Returns a list of DataFrames, one per table found.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    dataframes = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            for table in tables:
                cleaned = clean_table(table)

                if not cleaned or len(cleaned) < 2:
                    # Skip empty tables or tables with no data rows
                    continue

                headers = cleaned[0]
                rows = cleaned[1:]

                # Handle duplicate or blank column names
                seen = {}
                clean_headers = []
                for h in headers:
                    h = h if h else "unnamed"
                    seen[h] = seen.get(h, 0) + 1
                    clean_headers.append(f"{h}_{seen[h]}" if seen[h] > 1 else h)
                
                df = pd.DataFrame(rows, columns=clean_headers)
                df.insert(0, "page", page_num)  # tag which page it came from
                dataframes.append(df)

    return dataframes


def extract_text(pdf_path):
    """
    Extract raw text from a PDF page by page.
    Returns a list of dicts: {page, text}
    Used when no tables are found.
    """

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages_text.append({
                    "page": page_num,
                    "text": text.strip()
                })
    
    return pages_text



def extract(pdf_path):
    """
    Main entry point for PDF extraction.
    Tries tables first, falls back to raw text.
    Returns a dict with:
       - mode: 'table' or 'text'
       - data: list of DataFrames (table mode) or list of dicts (text_mode)
       - page_count: total pages in the PDF
       - source: filename
    """

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

    tables = extract_tables(pdf_path)

    if tables:
        return {
            "mode": "table",
            "data": tables,
            "page_count": page_count,
            "source": os.path.basename(pdf_path)
        }
    
    # Fallback to raw text
    text_data = extract_text(pdf_path)

    return {
        "mode": "text",
        "data": text_data,
        "page_count": page_count,
        "source": os.path.basename(pdf_path)
    }