from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "jp_topix500.csv"
HEADER = ["symbol", "name", "market", "sector", "industry", "theme", "note"]
MIN_VALID_ROWS = 450
MIN_NAMED_ROWS = 450
DEFAULT_INDEX_PAGE = "https://www.jpx.co.jp/english/markets/indices/topix/index.html"
DEFAULT_LISTED_ISSUES_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"


def clean(value: object) -> str:
    text = str(value or "").replace("\u3000", " ").strip()
    return "" if text.lower() == "nan" else text


def pick(row: dict[str, str], names: list[str]) -> str:
    for name in names:
        for key, value in row.items():
            if name.lower() in str(key).lower():
                result = clean(value)
                if result:
                    return result
    return ""


def decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def is_named(symbol: str, name: str) -> bool:
    normalized = clean(name).upper()
    return bool(normalized) and normalized not in {symbol.upper(), symbol.replace(".T", "").upper()}


def existing_quality() -> tuple[int, int]:
    if not OUT.exists():
        return 0, 0
    with OUT.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if clean(row.get("symbol"))]
    return len(rows), sum(1 for row in rows if is_named(clean(row.get("symbol")), clean(row.get("name"))))


def write_rows(rows: list[list[str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=OUT.parent) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)
        temp_path = Path(handle.name)
    temp_path.replace(OUT)


def session_get(url: str) -> requests.Response:
    response = requests.get(
        url,
        timeout=45,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; japan-stock-portal/4.0)",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
        },
    )
    response.raise_for_status()
    return response


def discover_csv_urls(index_page: str) -> list[str]:
    response = session_get(index_page)
    hrefs = re.findall(r'href=["\']([^"\']+\.csv(?:\?[^"\']*)?)["\']', response.text, flags=re.IGNORECASE)
    urls = [urljoin(index_page, href) for href in hrefs]
    preferred = [url for url in urls if "topix" in url.lower() and "weight" in url.lower()]
    return list(dict.fromkeys(preferred + urls))


def parse_source(url: str) -> dict[str, tuple[list[str], float]]:
    response = session_get(url)
    reader = csv.DictReader(io.StringIO(decode_csv(response.content)))
    collected: dict[str, tuple[list[str], float]] = {}
    for row in reader:
        code = pick(row, ["Local Code", "code", "コード"])
        name = pick(row, ["Issue Name", "銘柄名", "name", "Company"])
        sector = pick(row, ["33 Sector Name", "33業種区分", "Sector Name", "sector"])
        industry = pick(row, ["17 Sector Name", "17業種区分", "Industry"])
        weight_raw = pick(row, ["TOPIX Weight", "weight", "ウェイト"])
        digits = "".join(character for character in code if character.isdigit())
        if len(digits) < 4:
            continue
        symbol = digits[:4] + ".T"
        try:
            weight = float(weight_raw.replace("%", "").replace(",", ""))
        except ValueError:
            weight = 0.0
        label = sector or industry or "TOPIX 500"
        collected[symbol] = (
            [symbol, name or digits[:4], "JP", label, industry, label, "TOPIX component weight universe"],
            weight,
        )
    return collected


def fetch_listed_issue_metadata(url: str) -> dict[str, dict[str, str]]:
    response = session_get(url)
    frame = pd.read_excel(io.BytesIO(response.content), dtype=str)
    metadata: dict[str, dict[str, str]] = {}
    for _, source in frame.iterrows():
        row = {clean(key): clean(value) for key, value in source.items()}
        code = row.get("コード") or row.get("Code") or row.get("Local Code") or ""
        digits = "".join(character for character in code if character.isdigit())
        if len(digits) < 4:
            continue
        symbol = digits[:4] + ".T"
        metadata[symbol] = {
            "name": row.get("銘柄名") or row.get("Issue Name") or row.get("Company Name") or "",
            "sector": row.get("33業種区分") or row.get("33 Sector Name") or "",
            "industry": row.get("17業種区分") or row.get("17 Sector Name") or "",
        }
    return metadata


def apply_listed_issue_metadata(
    collected: dict[str, tuple[list[str], float]],
    metadata: dict[str, dict[str, str]],
) -> dict[str, tuple[list[str], float]]:
    enriched: dict[str, tuple[list[str], float]] = {}
    for symbol, (source_row, weight) in collected.items():
        row = list(source_row)
        details = metadata.get(symbol) or {}
        if clean(details.get("name")):
            row[1] = clean(details.get("name"))
        if clean(details.get("sector")):
            row[3] = clean(details.get("sector"))
            row[5] = clean(details.get("sector"))
        if clean(details.get("industry")):
            row[4] = clean(details.get("industry"))
        enriched[symbol] = (row, weight)
    return enriched


def main() -> None:
    configured = [url.strip() for url in os.getenv("TOPIX_SOURCE_URLS", "").split("|") if url.strip()]
    index_page = os.getenv("TOPIX_INDEX_PAGE_URL", DEFAULT_INDEX_PAGE).strip() or DEFAULT_INDEX_PAGE
    discovered: list[str] = []
    errors: list[str] = []
    listed_issues_url = os.getenv("TSE_LISTED_ISSUES_URL", DEFAULT_LISTED_ISSUES_URL).strip() or DEFAULT_LISTED_ISSUES_URL
    listed_metadata: dict[str, dict[str, str]] = {}
    try:
        listed_metadata = fetch_listed_issue_metadata(listed_issues_url)
    except Exception as error:
        errors.append(f"listed issues: {error.__class__.__name__}: {error}")
    try:
        discovered = discover_csv_urls(index_page)
    except Exception as error:
        errors.append(f"index discovery: {error.__class__.__name__}: {error}")

    urls = list(dict.fromkeys(configured + discovered))
    collected: dict[str, tuple[list[str], float]] = {}
    for url in urls:
        try:
            source_rows = parse_source(url)
            if len(source_rows) > len(collected):
                collected = source_rows
            if len(collected) >= MIN_VALID_ROWS:
                break
        except Exception as error:
            errors.append(f"{url}: {error.__class__.__name__}: {error}")

    collected = apply_listed_issue_metadata(collected, listed_metadata)
    ordered = sorted(collected.values(), key=lambda item: item[1], reverse=True)[:500]
    rows = [row for row, _ in ordered]
    named_rows = sum(1 for row in rows if is_named(row[0], row[1]))
    if len(rows) >= MIN_VALID_ROWS and named_rows >= MIN_NAMED_ROWS:
        write_rows(rows)
        print(f"Wrote {len(rows)} TOPIX large/mid-cap symbols; {named_rows} have company names")
        return

    count, existing_named = existing_quality()
    if count >= MIN_VALID_ROWS and existing_named >= MIN_NAMED_ROWS:
        print(f"TOPIX refresh failed; preserving {count} existing rows ({existing_named} named). {' | '.join(errors[-3:])}")
        return
    raise RuntimeError(
        f"TOPIX universe unavailable: found {len(rows)} rows ({named_rows} named); "
        f"existing file has {count} rows ({existing_named} named). "
        + " | ".join(errors[-3:])
    )


if __name__ == "__main__":
    main()
