from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "jp_topix500.csv"
HEADER = ["symbol", "name", "market", "sector", "industry", "theme", "note"]
MIN_VALID_ROWS = 450
DEFAULT_INDEX_PAGE = "https://www.jpx.co.jp/english/markets/indices/topix/index.html"


def clean(value: object) -> str:
    return str(value or "").replace("\u3000", " ").strip()


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


def existing_count() -> int:
    if not OUT.exists():
        return 0
    with OUT.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for row in csv.DictReader(handle) if (row.get("symbol") or "").strip())


def write_rows(rows: list[list[str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=OUT.parent) as handle:
        writer = csv.writer(handle)
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


def main() -> None:
    configured = [url.strip() for url in os.getenv("TOPIX_SOURCE_URLS", "").split("|") if url.strip()]
    index_page = os.getenv("TOPIX_INDEX_PAGE_URL", DEFAULT_INDEX_PAGE).strip() or DEFAULT_INDEX_PAGE
    discovered: list[str] = []
    errors: list[str] = []
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

    ordered = sorted(collected.values(), key=lambda item: item[1], reverse=True)[:500]
    rows = [row for row, _ in ordered]
    if len(rows) >= MIN_VALID_ROWS:
        write_rows(rows)
        print(f"Wrote {len(rows)} TOPIX large/mid-cap symbols with sector metadata")
        return

    count = existing_count()
    if count >= MIN_VALID_ROWS:
        print(f"TOPIX refresh failed; preserving {count} existing rows. {' | '.join(errors[-3:])}")
        return
    raise RuntimeError(
        f"TOPIX universe unavailable: found {len(rows)} rows and existing file has only {count}. "
        + " | ".join(errors[-3:])
    )


if __name__ == "__main__":
    main()
