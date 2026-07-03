import pandas as pd
import re


# ─── Known Catalog Field Aliases ──────────────────────────────────────────────

FIELD_MAP = {
    "product_name": ["product", "product name", "item", "item name", "name", "title", "product title"],
    "sku":          ["sku", "item #", "item no", "product code", "code", "part number", "part #", "model"],
    "description":  ["description", "details", "product description", "overview", "summary", "about"],
    "category":     ["category", "type", "product type", "department", "classification", "group"],
    "brand":        ["brand", "manufacturer", "make", "vendor", "supplier", "made by"],
    "price":        ["price", "unit price", "retail price", "cost", "msrp", "rate", "selling price"],
    "sale_price":   ["sale price", "discounted price", "offer price", "promo price", "special price"],
    "currency":     ["currency", "currency code"],
    "quantity":     ["quantity", "qty", "stock", "inventory", "units", "available", "in stock"],
    "weight":       ["weight", "weight (kg)", "weight (lbs)", "mass"],
    "dimensions":   ["dimensions", "size", "measurements", "l x w x h"],
    "color":        ["color", "colour", "finish", "shade"],
    "material":     ["material", "materials", "fabric", "composition"],
    "rating":       ["rating", "review score", "avg rating", "stars", "score"],
    "reviews":      ["reviews", "review count", "number of reviews", "total reviews"],
    "url":          ["url", "link", "product url", "product link", "page"],
    "image_url":    ["image", "image url", "photo", "photo url", "thumbnail"],
    "barcode":      ["barcode", "upc", "ean", "isbn", "asin"],
    "status":       ["status", "availability", "available", "in stock", "stock status"],
}


# ─── Field Normalizer ─────────────────────────────────────────────────────────

def normalize_columns(df, logger):
    """
    Rename DataFrame columns to standard catalog field names using FIELD_MAP.
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
        logger.warning("No recognized catalog columns found. Returning raw columns.")

    return df


# ─── Currency Cleaner ─────────────────────────────────────────────────────────

def clean_prices(df, logger):
    """
    Strip currency symbols and commas from price columns.
    Converts to float for calculations.
    """
    price_fields = ["price", "sale_price"]

    for field in price_fields:
        if field in df.columns:
            def clean_price(val):
                if pd.isna(val) or str(val).strip() == "":
                    return None
                cleaned = re.sub(r"[^\d.]", "", str(val))
                try:
                    return float(cleaned)
                except ValueError:
                    return None

            df[field] = df[field].apply(clean_price)
            logger.info(f"Cleaned price column: {field}")

    return df


# ─── Discount Calculator ──────────────────────────────────────────────────────

def calculate_discount(df, logger):
    """
    If both price and sale_price exist, calculate discount percentage.
    Adds a 'discount_pct' column.
    """
    if "price" not in df.columns or "sale_price" not in df.columns:
        return df

    def get_discount(row):
        try:
            price      = float(row["price"])
            sale_price = float(row["sale_price"])
            if price > 0 and sale_price < price:
                return round(((price - sale_price) / price) * 100, 2)
        except (TypeError, ValueError):
            pass
        return None

    df["discount_pct"] = df.apply(get_discount, axis=1)
    logger.info("Calculated discount_pct column.")
    return df


# ─── Quantity Cleaner ─────────────────────────────────────────────────────────

def clean_quantity(df, logger):
    """
    Normalize quantity/stock column to integers.
    Handles values like '10 units', 'Out of Stock', etc.
    """
    if "quantity" not in df.columns:
        return df

    def clean_qty(val):
        if pd.isna(val) or str(val).strip() == "":
            return None
        digits = re.sub(r"[^\d]", "", str(val))
        try:
            return int(digits)
        except ValueError:
            return None

    df["quantity"] = df["quantity"].apply(clean_qty)
    logger.info("Cleaned quantity column.")
    return df


# ─── SKU Normalizer ───────────────────────────────────────────────────────────

def normalize_sku(df, logger):
    """
    Uppercase and strip whitespace from SKU column.
    Flags missing SKUs.
    """
    if "sku" not in df.columns:
        return df

    df["sku"] = df["sku"].apply(
        lambda val: str(val).strip().upper() if pd.notna(val) and str(val).strip() != "" else "MISSING"
    )

    missing = (df["sku"] == "MISSING").sum()
    if missing:
        logger.warning(f"  {missing} missing SKU(s) flagged.")

    logger.info("Normalized SKU column.")
    return df


# ─── Duplicate Detector ───────────────────────────────────────────────────────

def flag_duplicates(df, logger):
    """
    Flag duplicate products based on SKU or product_name.
    Adds a 'duplicate' column.
    """
    if "sku" in df.columns:
        df["duplicate"] = df["sku"].duplicated(keep="first")
    elif "product_name" in df.columns:
        df["duplicate"] = df["product_name"].duplicated(keep="first")
    else:
        return df

    dup_count = df["duplicate"].sum()
    if dup_count:
        logger.warning(f"  {dup_count} duplicate product(s) flagged.")
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
    """Log a quick summary of the catalog data extracted."""
    logger.info("─── Catalog Summary ───────────────────────")
    logger.info(f"  Total products     : {len(df)}")

    if "price" in df.columns:
        price_col = pd.to_numeric(df["price"], errors="coerce")
        logger.info(f"  Avg price          : ${price_col.mean():,.2f}")
        logger.info(f"  Highest price      : ${price_col.max():,.2f}")
        logger.info(f"  Lowest price       : ${price_col.min():,.2f}")

    if "discount_pct" in df.columns:
        avg_disc = pd.to_numeric(df["discount_pct"], errors="coerce").mean()
        logger.info(f"  Avg discount       : {avg_disc:.1f}%")

    if "category" in df.columns:
        cats = df["category"].dropna().unique()
        logger.info(f"  Unique categories  : {len(cats)}")

    if "brand" in df.columns:
        brands = df["brand"].dropna().unique()
        logger.info(f"  Unique brands      : {len(brands)}")

    if "quantity" in df.columns:
        qty_col = pd.to_numeric(df["quantity"], errors="coerce")
        logger.info(f"  Total stock units  : {int(qty_col.sum())}")
        out_of_stock = (qty_col == 0).sum()
        if out_of_stock:
            logger.warning(f"  Out of stock items : {out_of_stock}")

    if "duplicate" in df.columns:
        logger.info(f"  Duplicates flagged : {df['duplicate'].sum()}")

    if "sku" in df.columns:
        missing_sku = (df["sku"] == "MISSING").sum()
        if missing_sku:
            logger.warning(f"  Missing SKUs       : {missing_sku}")

    logger.info("───────────────────────────────────────────")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def process(df, logger):
    """
    Main catalog mode pipeline.
    Called by main.py when --mode catalog is passed.
    """
    logger.info("Catalog mode activated.")

    df = drop_empty_rows(df, logger)
    df = normalize_columns(df, logger)
    df = clean_prices(df, logger)
    df = calculate_discount(df, logger)
    df = clean_quantity(df, logger)
    df = normalize_sku(df, logger)
    df = flag_duplicates(df, logger)
    log_summary(df, logger)

    logger.info(f"Catalog processing complete. {len(df)} product(s) returned.")
    return df