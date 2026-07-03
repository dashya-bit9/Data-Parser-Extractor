import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ─── Headers ──────────────────────────────────────────────────────────────────

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── URL Validator ────────────────────────────────────────────────────────────

def is_valid_url(url):
    """Check if a string is a valid HTTP/HTTPS URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ["http", "https"] and bool(parsed.netloc)
    except Exception:
        return False


# ─── Page Fetcher ─────────────────────────────────────────────────────────────

def fetch_page(url, timeout=15, logger=None):
    """
    Fetch a web page and return a BeautifulSoup object.
    Returns None if the request fails.
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        if logger:
            logger.info(f"  Fetched: {url} [{response.status_code}]")

        return soup

    except requests.exceptions.HTTPError as e:
        if logger:
            logger.error(f"  HTTP error fetching {url}: {e}")
    except requests.exceptions.ConnectionError:
        if logger:
            logger.error(f"  Connection error fetching {url}")
    except requests.exceptions.Timeout:
        if logger:
            logger.error(f"  Timeout fetching {url}")
    except Exception as e:
        if logger:
            logger.error(f"  Unexpected error fetching {url}: {e}")

    return None


# ─── Table Extractor ──────────────────────────────────────────────────────────

def extract_tables(soup, logger):
    """
    Extract all HTML tables from a page.
    Returns a list of DataFrames.
    """
    tables  = soup.find_all("table")
    results = []

    if not tables:
        if logger:
            logger.info("  No HTML tables found on page.")
        return results

    for i, table in enumerate(tables):
        rows = table.find_all("tr")
        if not rows:
            continue

        data = []
        for row in rows:
            cells = row.find_all(["th", "td"])
            data.append([cell.get_text(strip=True) for cell in cells])

        if len(data) < 2:
            continue

        headers  = data[0]
        body     = data[1:]

        # Handle mismatched column counts
        max_cols = max(len(row) for row in body)
        headers  = headers[:max_cols]
        while len(headers) < max_cols:
            headers.append(f"col_{len(headers) + 1}")

        df = pd.DataFrame(body, columns=headers)
        results.append(df)

        if logger:
            logger.info(f"  Table {i + 1}: {len(df)} row(s), {len(df.columns)} column(s).")

    return results


# ─── List Extractor ───────────────────────────────────────────────────────────

def extract_lists(soup, logger):
    """
    Extract all <ul> and <ol> lists from a page.
    Returns a DataFrame with list items.
    """
    items = []

    for tag in soup.find_all(["ul", "ol"]):
        list_type = tag.name.upper()
        for li in tag.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                items.append({
                    "type": list_type,
                    "item": text
                })

    if not items:
        if logger:
            logger.info("  No list items found on page.")
        return pd.DataFrame()

    df = pd.DataFrame(items)
    if logger:
        logger.info(f"  Extracted {len(df)} list item(s).")

    return df


# ─── Link Extractor ───────────────────────────────────────────────────────────

def extract_links(soup, base_url, logger):
    """
    Extract all hyperlinks from a page.
    Returns a DataFrame with text and URL columns.
    """
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)

        # Build absolute URL
        full_url = urljoin(base_url, href)

        if not is_valid_url(full_url):
            continue

        links.append({
            "text": text,
            "url":  full_url
        })

    if not links:
        if logger:
            logger.info("  No links found on page.")
        return pd.DataFrame()

    df = pd.DataFrame(links).drop_duplicates(subset=["url"])
    if logger:
        logger.info(f"  Extracted {len(df)} unique link(s).")

    return df


# ─── Contact Info Extractor ───────────────────────────────────────────────────

def extract_contact_info(soup, logger):
    """
    Scan page text for emails and phone numbers.
    Returns a DataFrame with type and value columns.
    """
    text    = soup.get_text(separator=" ")
    results = []

    # Email pattern
    emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w{2,}", text)
    for email in set(emails):
        results.append({"type": "email", "value": email})

    # Phone pattern
    phones = re.findall(
        r"(\+?\d{1,3}[\s\-]?)?(\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4})", text
    )
    for match in phones:
        phone = "".join(match).strip()
        if phone:
            results.append({"type": "phone", "value": phone})

    if not results:
        if logger:
            logger.info("  No contact info found on page.")
        return pd.DataFrame()

    df = pd.DataFrame(results).drop_duplicates(subset=["value"])
    if logger:
        logger.info(f"  Found {len(df)} contact info item(s).")

    return df


# ─── Text Extractor ───────────────────────────────────────────────────────────

def extract_text(soup, logger):
    """
    Extract all visible paragraph text from a page.
    Returns a DataFrame with paragraph text.
    """
    paragraphs = []

    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        text = tag.get_text(strip=True)
        if text:
            paragraphs.append({
                "tag":  tag.name,
                "text": text
            })

    if not paragraphs:
        if logger:
            logger.info("  No paragraph text found on page.")
        return pd.DataFrame()

    df = pd.DataFrame(paragraphs)
    if logger:
        logger.info(f"  Extracted {len(df)} paragraph(s).")

    return df


# ─── Multi-URL Batch Scraper ──────────────────────────────────────────────────

def scrape_urls(urls, extract_type="tables", logger=None):
    """
    Scrape a list of URLs and combine results into one DataFrame.
    extract_type options: 'tables', 'links', 'contacts', 'lists', 'text'
    """
    all_dfs = []

    for url in urls:
        if not is_valid_url(url):
            if logger:
                logger.warning(f"  Skipping invalid URL: {url}")
            continue

        if logger:
            logger.info(f"Scraping: {url}")

        soup = fetch_page(url, logger=logger)
        if soup is None:
            continue

        if extract_type == "tables":
            dfs = extract_tables(soup, logger)
            all_dfs.extend(dfs)

        elif extract_type == "links":
            df = extract_links(soup, url, logger)
            if not df.empty:
                df.insert(0, "source_url", url)
                all_dfs.append(df)

        elif extract_type == "contacts":
            df = extract_contact_info(soup, logger)
            if not df.empty:
                df.insert(0, "source_url", url)
                all_dfs.append(df)

        elif extract_type == "lists":
            df = extract_lists(soup, logger)
            if not df.empty:
                df.insert(0, "source_url", url)
                all_dfs.append(df)

        elif extract_type == "text":
            df = extract_text(soup, logger)
            if not df.empty:
                df.insert(0, "source_url", url)
                all_dfs.append(df)

        else:
            if logger:
                logger.warning(f"  Unknown extract_type: {extract_type}")

    if not all_dfs:
        if logger:
            logger.warning("No data extracted from any URL.")
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    if logger:
        logger.info(f"Scraping complete. {len(combined)} total row(s) across {len(urls)} URL(s).")

    return combined


# ─── URL File Loader ──────────────────────────────────────────────────────────

def load_urls_from_file(filepath):
    """
    Load a list of URLs from a plain text file, one URL per line.
    Returns a list of valid URLs.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"URL file not found: {filepath}")

    with open(filepath, "r") as f:
        lines = [line.strip() for line in f.readlines()]

    urls = [line for line in lines if is_valid_url(line)]
    return urls


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def extract(input_source, extract_type="tables", logger=None):
    """
    Main web scraper entry point.
    input_source can be:
        - A single URL string
        - A path to a .txt file containing one URL per line

    Returns a dict matching the same format as pdf_extractor.extract():
        - mode: 'table' or 'text'
        - data: list of DataFrames
        - page_count: number of URLs scraped
        - source: input source
    """
    # ── Load URLs ──
    if os.path.isfile(input_source):
        urls = load_urls_from_file(input_source)
        if logger:
            logger.info(f"Loaded {len(urls)} URL(s) from file: {input_source}")
    elif is_valid_url(input_source):
        urls = [input_source]
    else:
        raise ValueError(f"Input is not a valid URL or URL file: {input_source}")

    if not urls:
        raise ValueError("No valid URLs found to scrape.")

    # ── Scrape ──
    df = scrape_urls(urls, extract_type=extract_type, logger=logger)

    if df.empty:
        return {
            "mode":       "text",
            "data":       [],
            "page_count": len(urls),
            "source":     input_source
        }

    return {
        "mode":       "table",
        "data":       [df],
        "page_count": len(urls),
        "source":     input_source
    }