import pandas as pd
import re


# ─── Known Invoice Field Aliases ─────────────────────────────────────────────
# Maps common column name variations to a standard field name.
# When we add AI later, this becomes a fallback for known patterns.

FIELD_MAP = {
    "invoice_number": ["invoice #", "invoice no", "invoice number", "inv #", "inv no", "number"],
    "date":           ["date", "invoice date", "issue date", "billing date", "dated"],
    "due_date":       ["due date", "payment due", "due by", "due"],
    "vendor":         ["vendor", "supplier", "from", "billed by", "company", "business name"],
    "client":         ["client", "bill to", "billed to", "customer", "to"],
    "description":    ["description", "item", "details", "service", "product", "particulars"],
    "quantity":       ["quantity", "qty", "units", "count"],
    "unit_price":     ["unit price", "rate", "price", "cost", "unit cost"],
    "amount":         ["amount", "total", "subtotal", "line total", "ext price", "extended price"],
    "tax":            ["tax", "vat", "gst", "tax amount"],
    "discount":       ["discount", "disc", "deduction"],
    "total":          ["grand total", "total due", "balance due", "amount due", "total amount"],
}


# ─── Field Normalizer ─────────────────────────────────────────────────────────

def normalize_columns(df, logger):
    """
    Attempt to rename DataFrame columns to standard invoice field names
    using FIELD_MAP aliases. Unrecognized columns are left as-is.
    """
    rename_map = {}
    lowered = {col: col.lower().strip() for col in df.columns}

    for col, lower_col in lowered.items():
        for standard_name, aliases in FIELD_MAP.items():
            if lower_col in aliases:
                rename_map[col] = standard_name
                break

    if rename_map:
        df = df.rename(columns=rename_map)
        logger.info(f"Mapped columns: {rename_map}")
    else:
        logger.warning("No recognized invoice columns found. Returning raw columns.")

    return df


# ─── Currency Cleaner ─────────────────────────────────────────────────────────

def clean_currency(val):
    """
    Strip currency symbols, commas, and whitespace from a value.
    Returns a float or None if it can't be converted.
    """
    if pd.isna(val) or str(val).strip() == "":
        return None
    cleaned = re.sub(r"[^\d.]", "", str(val))
    try:
        return float(cleaned)
    except ValueError:
        return None


# ─── Numeric Column Cleaner ───────────────────────────────────────────────────

def clean_numeric_columns(df, logger):
    """
    Find currency/numeric invoice columns and clean them to floats.
    """
    numeric_fields = ["unit_price", "amount", "tax", "discount", "total", "quantity"]

    for field in numeric_fields:
        if field in df.columns:
            df[field] = df[field].apply(clean_currency)
            logger.info(f"Cleaned numeric column: {field}")

    return df


# ─── Empty Row Filter ─────────────────────────────────────────────────────────

def drop_empty_rows(df, logger):
    """
    Drop rows where every cell is empty or None.
    """
    before = len(df)
    df = df.dropna(how="all")
    df = df[~(df == "").all(axis=1)]
    after = len(df)

    if before != after:
        logger.info(f"Dropped {before - after} empty row(s).")

    return df


# ─── Summary ─────────────────────────────────────────────────────────────────

def log_summary(df, logger):
    """
    Log a quick financial summary if the right columns exist.
    """
    logger.info("─── Invoice Summary ───────────────────────")

    if "total" in df.columns:
        total_col = pd.to_numeric(df["total"], errors="coerce")
        logger.info(f"  Total due (sum)    : ${total_col.sum():,.2f}")
        logger.info(f"  Highest invoice    : ${total_col.max():,.2f}")
        logger.info(f"  Lowest invoice     : ${total_col.min():,.2f}")

    if "tax" in df.columns:
        tax_col = pd.to_numeric(df["tax"], errors="coerce")
        logger.info(f"  Total tax          : ${tax_col.sum():,.2f}")

    if "vendor" in df.columns:
        vendors = df["vendor"].dropna().unique()
        logger.info(f"  Vendors found      : {len(vendors)}")

    logger.info("───────────────────────────────────────────")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def process(df, logger):
    """
    Main invoice mode pipeline.
    Called by main.py when --mode invoice is passed.
    """
    logger.info("Invoice mode activated.")

    df = drop_empty_rows(df, logger)
    df = normalize_columns(df, logger)
    df = clean_numeric_columns(df, logger)
    log_summary(df, logger)

    logger.info(f"Invoice processing complete. {len(df)} row(s) returned.")
    return df