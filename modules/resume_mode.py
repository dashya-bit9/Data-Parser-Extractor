import pandas as pd
import re


# ─── Known Resume Field Aliases ───────────────────────────────────────────────

FIELD_MAP = {
    "full_name":    ["name", "full name", "candidate", "applicant", "candidate name"],
    "email":        ["email", "e-mail", "email address", "contact email"],
    "phone":        ["phone", "telephone", "mobile", "cell", "contact number", "phone number"],
    "location":     ["location", "address", "city", "city/state", "region", "based in"],
    "title":        ["title", "job title", "position", "role", "current role", "current title"],
    "company":      ["company", "employer", "organization", "current employer", "current company"],
    "experience":   ["experience", "years of experience", "years experience", "work experience", "exp"],
    "skills":       ["skills", "technical skills", "key skills", "competencies", "technologies"],
    "education":    ["education", "degree", "qualification", "university", "college", "school"],
    "linkedin":     ["linkedin", "linkedin url", "linkedin profile", "profile url"],
    "summary":      ["summary", "objective", "profile", "about", "bio", "professional summary"],
}


# ─── Field Normalizer ─────────────────────────────────────────────────────────

def normalize_columns(df, logger):
    """
    Rename DataFrame columns to standard resume field names using FIELD_MAP.
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
        logger.warning("No recognized resume columns found. Returning raw columns.")

    return df


# ─── Email Validator ──────────────────────────────────────────────────────────

def validate_emails(df, logger):
    """
    Flag rows where the email column doesn't look like a valid email.
    Adds a 'email_valid' column for review.
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
    Normalize phone numbers to digits only format.
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


# ─── Skills Normalizer ────────────────────────────────────────────────────────

def normalize_skills(df, logger):
    """
    Clean up skills column — strip extra whitespace and
    normalize comma/semicolon separators to comma only.
    """
    if "skills" not in df.columns:
        return df

    def clean_skills(val):
        if pd.isna(val) or str(val).strip() == "":
            return ""
        # Replace semicolons and pipes with commas
        normalized = re.sub(r"[;|]", ",", str(val))
        # Clean up spacing around commas
        parts = [s.strip() for s in normalized.split(",") if s.strip()]
        return ", ".join(parts)

    df["skills"] = df["skills"].apply(clean_skills)
    logger.info("Normalized skills column.")
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
    """Log a quick summary of the resume data extracted."""
    logger.info("─── Resume Summary ────────────────────────")
    logger.info(f"  Total candidates   : {len(df)}")

    if "email_valid" in df.columns:
        valid   = (df["email_valid"] == "valid").sum()
        invalid = (df["email_valid"] == "invalid").sum()
        missing = (df["email_valid"] == "missing").sum()
        logger.info(f"  Valid emails       : {valid}")
        logger.info(f"  Invalid emails     : {invalid}")
        logger.info(f"  Missing emails     : {missing}")

    if "location" in df.columns:
        locations = df["location"].dropna().unique()
        logger.info(f"  Unique locations   : {len(locations)}")

    if "title" in df.columns:
        titles = df["title"].dropna().unique()
        logger.info(f"  Unique job titles  : {len(titles)}")

    if "skills" in df.columns:
        all_skills = df["skills"].dropna().str.split(",").explode().str.strip()
        top_skills = all_skills.value_counts().head(5)
        logger.info(f"  Top skills found   : {', '.join(top_skills.index.tolist())}")

    logger.info("───────────────────────────────────────────")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def process(df, logger):
    """
    Main resume mode pipeline.
    Called by main.py when --mode resume is passed.
    """
    logger.info("Resume mode activated.")

    df = drop_empty_rows(df, logger)
    df = normalize_columns(df, logger)
    df = validate_emails(df, logger)
    df = clean_phones(df, logger)
    df = normalize_skills(df, logger)
    log_summary(df, logger)

    logger.info(f"Resume processing complete. {len(df)} candidate(s) returned.")
    return df