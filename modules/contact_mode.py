import pandas as pd
import re


# ─── Known Contact Field Aliases ──────────────────────────────────────────────

FIELD_MAP = {
    "full_name":    ["name", "full name", "contact", "contact name", "person", "individual"],
    "first_name":   ["first name", "first", "given name"],
    "last_name":    ["last name", "last", "surname", "family name"],
    "email":        ["email", "e-mail", "email address", "contact email", "work email"],
    "phone":        ["phone", "telephone", "mobile", "cell", "direct", "contact number", "phone number"],
    "company":      ["company", "organization", "organisation", "employer", "business", "firm"],
    "title":        ["title", "job title", "position", "role", "designation"],
    "department":   ["department", "dept", "division", "team", "unit"],
    "address":      ["address", "street", "street address", "mailing address"],
    "city":         ["city", "town", "municipality"],
    "state":        ["state", "province", "region"],
    "zip":          ["zip", "zip code", "postal code", "postcode"],
    "country":      ["country", "nation"],
    "website":      ["website", "url", "web", "site", "homepage"],
    "linkedin":     ["linkedin", "linkedin url", "linkedin profile"],
    "twitter":      ["twitter", "twitter handle", "x handle"],
    "notes":        ["notes", "comments", "remarks", "additional info"],
}


# ─── Field Normalizer ─────────────────────────────────────────────────────────

def normalize_columns(df, logger):
    """
    Rename DataFrame columns to standard contact field names using FIELD_MAP.
    Unrecognized columns are left as-is.
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
        logger.warning("No recognized contact columns found. Returning raw columns.")

    return df


# ─── Name Splitter ────────────────────────────────────────────────────────────

def split_full_name(df, logger):
    """
    If full_name exists but first_name/last_name don't,
    split it into separate columns automatically.
    """
    if "full_name" not in df.columns:
        return df
    if "first_name" in df.columns and "last_name" in df.columns:
        return df

    def split_name(val):
        if pd.isna(val) or str(val).strip() == "":
            return pd.Series(["", ""])
        parts = str(val).strip().split()
        if len(parts) == 1:
            return pd.Series([parts[0], ""])
        return pd.Series([parts[0], " ".join(parts[1:])])

    df[["first_name", "last_name"]] = df["full_name"].apply(split_name)
    logger.info("Split full_name into first_name and last_name.")
    return df


# ─── Email Validator ──────────────────────────────────────────────────────────

def validate_emails(df, logger):
    """
    Flag rows where the email column doesn't look like a valid email.
    Adds an 'email_valid' column for review.
    """
    if "email" not in df.columns:
        return df

    email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")

    def check_email(val):
        if pd.isna(val) or str(val).strip() == "":
            return "missing"
        return "valid" if email_pattern.match(str(val).strip()) else "invalid"

    df["email_valid"] = df["email"].apply(check_email)

    invalid_count = (df["email_valid"] == "invalid").sum()
    missing_count = (df["email_valid"] == "missing").sum()

    if invalid_count:
        logger.warning(f"  {invalid_count} invalid email(s) flagged.")
    if missing_count:
        logger.warning(f"  {missing_count} missing email(s) flagged.")

    return df


# ─── Phone Cleaner ────────────────────────────────────────────────────────────

def clean_phones(df, logger):
    """
    Normalize phone numbers to digits only.
    Example: (910) 555-1234 -> 9105551234
    """
    if "phone" not in df.columns:
        return df

    def clean_phone(val):
        if pd.isna(val) or str(val).strip() == "":
            return ""
        return re.sub(r"\D", "", str(val))

    df["phone"] = df["phone"].apply(clean_phone)
    logger.info("Cleaned phone column.")
    return df


# ─── Address Builder ──────────────────────────────────────────────────────────

def build_full_address(df, logger):
    """
    If address parts exist as separate columns, combine them
    into a single 'full_address' column for clean output.
    """
    parts = ["address", "city", "state", "zip", "country"]
    available = [p for p in parts if p in df.columns]

    if len(available) < 2:
        return df

    def combine(row):
        pieces = [str(row[p]).strip() for p in available if str(row[p]).strip() not in ("", "nan")]
        return ", ".join(pieces)

    df["full_address"] = df.apply(combine, axis=1)
    logger.info(f"Built full_address from: {available}")
    return df


# ─── Duplicate Detector ───────────────────────────────────────────────────────

def flag_duplicates(df, logger):
    """
    Flag duplicate contacts based on email or full_name.
    Adds a 'duplicate' column marked True/False.
    """
    if "email" in df.columns:
        df["duplicate"] = df["email"].duplicated(keep="first")
    elif "full_name" in df.columns:
        df["duplicate"] = df["full_name"].duplicated(keep="first")
    else:
        return df

    dup_count = df["duplicate"].sum()
    if dup_count:
        logger.warning(f"  {dup_count} duplicate contact(s) flagged.")
    else:
        logger.info("  No duplicates found.")

    return df


# ─── Empty Row Filter ─────────────────────────────────────────────────────────

def drop_empty_rows(df, logger):
    """Drop rows where every cell is empty or None."""
    before = len(df)
    df = df.dropna(how="all")
    df = df[~(df == "").all(axis=1)]
    after = len(df)

    if before != after:
        logger.info(f"Dropped {before - after} empty row(s).")

    return df


# ─── Summary ──────────────────────────────────────────────────────────────────

def log_summary(df, logger):
    """Log a quick summary of the contact list extracted."""
    logger.info("─── Contact Summary ───────────────────────")
    logger.info(f"  Total contacts     : {len(df)}")

    if "email_valid" in df.columns:
        valid   = (df["email_valid"] == "valid").sum()
        invalid = (df["email_valid"] == "invalid").sum()
        missing = (df["email_valid"] == "missing").sum()
        logger.info(f"  Valid emails       : {valid}")
        logger.info(f"  Invalid emails     : {invalid}")
        logger.info(f"  Missing emails     : {missing}")

    if "duplicate" in df.columns:
        logger.info(f"  Duplicates flagged : {df['duplicate'].sum()}")

    if "company" in df.columns:
        companies = df["company"].dropna().unique()
        logger.info(f"  Unique companies   : {len(companies)}")

    if "city" in df.columns:
        cities = df["city"].dropna().unique()
        logger.info(f"  Unique cities      : {len(cities)}")

    logger.info("───────────────────────────────────────────")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def process(df, logger):
    """
    Main contact mode pipeline.
    Called by main.py when --mode contact is passed.
    """
    logger.info("Contact mode activated.")

    df = drop_empty_rows(df, logger)
    df = normalize_columns(df, logger)
    df = split_full_name(df, logger)
    df = validate_emails(df, logger)
    df = clean_phones(df, logger)
    df = build_full_address(df, logger)
    df = flag_duplicates(df, logger)
    log_summary(df, logger)

    logger.info(f"Contact processing complete. {len(df)} contact(s) returned.")
    return df