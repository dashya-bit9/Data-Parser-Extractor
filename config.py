import os


#_______________BASE PATHS___________

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR=os.path.join(BASE_DIR, "output")
LOG_DIR=os.path.join(BASE_DIR, "logs")


# Create them if they don't exist yet
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)



#__________________SUPPORTED INPUT TYPES____________

SUPPORTED_EXTENSIONS = {
    "document": [".pdf", ".docx"],
    "spreadsheet": [".xlsx", ".xls", ".csv"],
    "image": [".png", ".jpg", ".jpeg", ".tiff", ".bmp"],
    "web": ["http://", "https://"]
}


#_______________OUTPUT FORMATS_____________

OUTPUT_FORMATS = ["csv", "json", "xlsx"]
DEFAULT_FORMAT = "csv"


#_________________JOB MODES____________

MODES = {
    "invoice": "modes.invoice_mode",
    "resume": "modes.resume_mode",
    "contact": "modes.contact_mode",
    "catalog": "modes.catalog_mode",
    "general": None           # No mode - raw extraction, no field mapping
}

DEFAULT_MODE = "general"


#________________LOGGING________________

LOG_ENABLED=True
LOG_LEVEL="INFO"    #DEBUG, INFO, WARNING, ERROR

#_______________EXTRACTION SETTINGS_________

# Table extraction
MIN_ROWS=1         # Minimun data rows required to keep a table
MIN_COLS=1         # Minimun columns required to keep a table


# Text extraction fallback
TEXT_FALLBACK=True   # If no tables found, fall back to raw text


# OCR (will be used by ocr_extractor.py)
OCR_ENABLED=True
OCR_LANGUAGE="eng"     #Tesseract language code


#__________________BATCH PROCESSING_____________

BATCH_ENABLED=True
BATCH_FILE_LIMIT=500     # Max files per batch job
SKIP_ON_ERROR=True       # If one file fails, keep going instead of stopping


#_____________OUTPUT NAMING___________

def get_output_path(filename, fmt):
    """
    Build a full output file path.
    Example: get_output_path("invoice_scan", "csv")
    --> /path/to/output/invoice_scan.csv
    """

    name = os.path.splitext(filename)[0]
    return os.path.join(OUTPUT_DIR, f"{name}.{fmt}")


def get_log_path(filename):
    """
    Build a full log file path.
    Example: get_log_path("invoice_scan")
    --> /path/to/logs/invoice_scan.log
    """

    name = os.path.splitext(filename)[0]
    return os.path.join(LOG_DIR, f"{name}.log")

