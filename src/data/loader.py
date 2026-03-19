"""
RAR extraction and CSV file indexing for NIFTY option data.

File naming: NIFTY{YY}{MM}{DD}{STRIKE}{TYPE}.csv
  - YY: 2-digit year, MM: 2-digit month (01-12), DD: 2-digit expiry day
  - STRIKE: numeric strike price, TYPE: CE or PE

RAR path: {DATA_ROOT}/{YEAR}/Index Option IEoD - {YYMM}.rar
"""

import os
import re
import subprocess
from pathlib import Path

DATA_ROOT = Path("/Users/ashwanthkumar/Downloads/eodieod.com-historical-data")
CACHE_DIR = Path("/Users/ashwanthkumar/trading/learn-trading-from-x/.cache/extracted")

# Regex: NIFTY + YY + MM(2-digit) + DD(2-digit) + STRIKE(digits) + TYPE
FILENAME_RE = re.compile(r"^NIFTY(\d{2})(\d{2})(\d{2})(\d+)(CE|PE)\.csv$")


def rar_path(year: int, month: int) -> Path:
    yy = str(year)[-2:]
    mm = f"{month:02d}"
    return DATA_ROOT / str(year) / f"Index Option IEoD - {yy}{mm}.rar"


def cache_dir_for(year: int, month: int) -> Path:
    yy = str(year)[-2:]
    mm = f"{month:02d}"
    return CACHE_DIR / f"{yy}{mm}"


def extract_month(year: int, month: int) -> Path:
    """
    Extract NIFTY CSVs from the monthly RAR into the cache directory.
    Skips extraction if cache directory already exists and is non-empty.
    Returns the cache directory path.
    """
    dest = cache_dir_for(year, month)
    rar = rar_path(year, month)

    if not rar.exists():
        raise FileNotFoundError(f"RAR not found: {rar}")

    if dest.exists() and any(dest.iterdir()):
        return dest  # already extracted

    dest.mkdir(parents=True, exist_ok=True)

    # Use unrar to extract only NIFTY* files (skip BANKNIFTY, FINNIFTY, MIDCPNIFTY)
    # unrar x -inul <archive> <pattern> <dest>/
    cmd = ["unrar", "x", "-inul", str(rar), "NIFTY*.csv", str(dest) + "/"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode not in (0, 1):  # 1 = some files skipped (ok)
        raise RuntimeError(f"unrar failed (rc={result.returncode}): {result.stderr}")

    # unrar extracts into a subdirectory matching the RAR's internal dir
    # Move files up if they landed in a subdir
    _flatten_subdir(dest)

    return dest


def _flatten_subdir(dest: Path) -> None:
    """If unrar created a subdirectory, move all CSVs up into dest."""
    subdirs = [p for p in dest.iterdir() if p.is_dir()]
    if not subdirs:
        return
    for subdir in subdirs:
        for f in subdir.glob("*.csv"):
            target = dest / f.name
            if not target.exists():
                f.rename(target)
        # Remove subdir if empty
        try:
            subdir.rmdir()
        except OSError:
            pass


def index_nifty_files(year: int, month: int) -> dict:
    """
    Scan extracted CSVs and return a nested dict:
        { expiry_date_str (YYYY-MM-DD) → { strike (int) → { 'CE': Path, 'PE': Path } } }

    expiry_date_str uses the full date inferred from YY+MM+DD in the filename.
    """
    dest = cache_dir_for(year, month)
    if not dest.exists():
        extract_month(year, month)

    index: dict = {}

    for f in dest.glob("NIFTY*.csv"):
        m = FILENAME_RE.match(f.name)
        if not m:
            continue

        yy, exp_mm, exp_dd, strike_str, opt_type = m.groups()
        full_year = 2000 + int(yy)
        expiry_key = f"{full_year}-{exp_mm}-{exp_dd}"
        strike = int(strike_str)

        index.setdefault(expiry_key, {}).setdefault(strike, {})[opt_type] = f

    return index


def get_available_months(year: int) -> list[int]:
    """Return sorted list of months for which RAR files exist."""
    year_dir = DATA_ROOT / str(year)
    if not year_dir.exists():
        return []
    months = []
    for f in year_dir.glob("Index Option IEoD - *.rar"):
        m = re.search(r"(\d{2})(\d{2})\.rar$", f.name)
        if m:
            months.append(int(m.group(2)))
    return sorted(months)
