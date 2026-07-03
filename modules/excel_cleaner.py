import os
import re
import pandas as pd


# ─── Sheet Loader ─────────────────────────────────────────────────────────────

def load_sheets(filepath, logger):
    """
    Load all sheets from an Excel file or a CSV.
    Returns a dict of {sheet_name: DataFrame}.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".csv":
        df = pd.read_csv(filepath, dtype=str)
        logger.info(f"  Loaded CSV: {len(df)} row(s), {len(df.columns)} column(s).")
        return {"Sheet1": df}

    elif ext in [".xlsx", ".xls"]:
        xl      = pd.ExcelFile(filepath)
        sheets  = {}

        for name in xl.sheet_names:
            df = xl.parse(name, dtype=str)
            logger.info(f"  Loaded sheet '{name}': {len(df)} row(s), {len(df.columns)} column(s).")
            sheets[name] = df

        return sheets

    else:
        raise ValueError(f"Unsupported spreadsheet format: {ext}")


# ─── Header Fixer ─────────────────────────────────────────────────────────────

def fix_headers(df, logger):
    """
    Detect and fix common header problems:
    - Unnamed columns (Unnamed: 0, Unnamed: 1, etc.)
    - Duplicate column names
    - Blank column names
    - Whitespace in column names
    """
    new_cols  = []
    seen      = {}

    for col in df.columns:
        # Clean whitespace
        col = str(col).strip()

        # Replace Unnamed columns
        if col.startswith("Unnamed:") or col == "":
            col = "unnamed"

        # Handle duplicates
        seen[col] = seen.get(col, 0) + 1
        new_cols.append(f"{col}_{seen[col]}" if seen[col] > 1 else col)

    if list(df.columns) != new_cols:
        logger.info(f"  Fixed headers: {list(df.columns)} → {new_cols}")

    df.columns = new_cols
    return df


# ─── Empty Row and Column Cleaner ─────────────────────────────────────────────

def drop_empty(df, logger):
    """
    Drop rows and columns that are entirely empty.
    """
    before_rows = len(df)
    before_cols = len(df.columns)

    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")
    df = df[~(df == "").all(axis=1)]
    df = df.loc[:, ~(df == "").all()]

    dropped_rows = before_rows - len(df)
    dropped_cols = before_cols - len(df.columns)

    if dropped_rows:
        logger.info(f"  Dropped {dropped_rows} empty row(s).")
    if dropped_cols:
        logger.info(f"  Dropped {dropped_cols} empty column(s).")

    return df


# ─── Whitespace Cleaner ───────────────────────────────────────────────────────

def clean_whitespace(df, logger):
    """
    Strip leading/trailing whitespace from all string cells.
    Collapse internal multiple spaces to single space.
    """
    def clean_cell(val):
        if pd.isna(val) or str(val).strip() == "":
            return ""
        return re.sub(r"\s+", " ", str(val).strip())

    df = df.map(clean_cell)
    logger.info("  Cleaned whitespace in all cells.")
    return df


# ─── Duplicate Row Detector ───────────────────────────────────────────────────

def flag_duplicates(df, logger):
    """
    Flag fully duplicate rows.
    Adds a 'duplicate_row' column marked True/False.
    Keeps the first occurrence as the original.
    """
    df["duplicate_row"] = df.duplicated(keep="first")
    dup_count = df["duplicate_row"].sum()

    if dup_count:
        logger.warning(f"  {dup_count} duplicate row(s) flagged.")
    else:
        logger.info("  No duplicate rows found.")

    return df


# ─── Data Type Detector ───────────────────────────────────────────────────────

def detect_and_convert_types(df, logger):
    """
    Attempt to convert columns to their most appropriate data type.
    - Numeric strings → float
    - Date strings → datetime
    - Everything else stays as string
    """
    for col in df.columns:
        if col == "duplicate_row":
            continue

        # Try numeric
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() > len(df) * 0.5:
            df[col] = converted
            logger.info(f"  Converted '{col}' to numeric.")
            continue

        # Try datetime
        try:
            converted_dt = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
            if converted_dt.notna().sum() > len(df) * 0.5:
                df[col] = converted_dt
                logger.info(f"  Converted '{col}' to datetime.")
                continue
        except Exception:
            pass

    return df


# ─── Header Row Detector ──────────────────────────────────────────────────────

def detect_misplaced_header(df, logger):
    """
    Detect if the real header row is buried inside the data
    because the Excel file had extra rows above it.
    Looks for a row where most values match the current column names' pattern.
    """
    for i, row in df.iterrows():
        values      = [str(v).strip().lower() for v in row.values]
        non_numeric = sum(1 for v in values if not re.match(r"^[\d\.\,\$\%\-]+$", v))

        # If a data row looks more like headers (mostly text, no numbers)
        if non_numeric == len(values) and i > 0:
            logger.warning(
                f"  Possible misplaced header detected at row {i}. "
                f"Consider manually inspecting the source file."
            )
            break

    return df


# ─── Column Name Normalizer ───────────────────────────────────────────────────

def normalize_column_names(df, logger):
    """
    Standardize column names to snake_case.
    Example: 'First Name' → 'first_name', 'EMAIL ADDRESS' → 'email_address'
    """
    new_cols = []
    for col in df.columns:
        col = str(col).strip().lower()
        col = re.sub(r"[\s\-]+", "_", col)
        col = re.sub(r"[^\w]", "", col)
        new_cols.append(col)

    if list(df.columns) != new_cols:
        logger.info(f"  Normalized column names to snake_case.")

    df.columns = new_cols
    return df


# ─── Summary ──────────────────────────────────────────────────────────────────

def log_summary(df, sheet_name, logger):
    """Log a quick summary of the cleaned sheet."""
    logger.info(f"─── Sheet Summary: {sheet_name} ───────────────")
    logger.info(f"  Rows             : {len(df)}")
    logger.info(f"  Columns          : {len(df.columns)}")

    if "duplicate_row" in df.columns:
        logger.info(f"  Duplicates       : {df['duplicate_row'].sum()}")

    null_counts = df.isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    if not cols_with_nulls.empty:
        for col, count in cols_with_nulls.items():
            logger.warning(f"  Missing values in '{col}': {count}")

    logger.info("───────────────────────────────────────────")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def extract(filepath, logger):
    """
    Main Excel/CSV entry point.
    Cleans and restructures spreadsheet data.
    Returns a dict matching the same format as pdf_extractor.extract():
        - mode: 'table' or 'text'
        - data: list of DataFrames
        - page_count: number of sheets processed
        - source: filename
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    filename = os.path.basename(filepath)
    logger.info(f"Opening spreadsheet: {filename}")

    sheets     = load_sheets(filepath, logger)
    dataframes = []

    for sheet_name, df in sheets.items():
        logger.info(f"Cleaning sheet: '{sheet_name}'")

        df = fix_headers(df, logger)
        df = drop_empty(df, logger)
        df = clean_whitespace(df, logger)
        df = detect_misplaced_header(df, logger)
        df = normalize_column_names(df, logger)
        df = detect_and_convert_types(df, logger)
        df = flag_duplicates(df, logger)

        log_summary(df, sheet_name, logger)

        if not df.empty:
            df.insert(0, "sheet", sheet_name)
            dataframes.append(df)

    if not dataframes:
        return {
            "mode":       "text",
            "data":       [],
            "page_count": 0,
            "source":     filename
        }

    return {
        "mode":       "table",
        "data":       dataframes,
        "page_count": len(dataframes),
        "source":     filename
    }