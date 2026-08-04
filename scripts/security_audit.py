from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "security-audit.json"
VENDOR_CHART = ROOT / "vendor" / "lightweight-charts" / "lightweight-charts.standalone.production.js"
VENDOR_SHA256 = "c0992580867c4912cc9385b3c2728315bcc1a76c7f1087dca908430fccdf31d7"
ALLOWED_DOMAINS = {
    "api.nasdaq.com",
    "disclosure2.edinet-fsa.go.jp",
    "en.wikipedia.org",
    "finance.yahoo.co.jp",
    "jp.tradingview.com",
    "kabutan.jp",
    "release.tdnet.info",
    "www.release.tdnet.info",
    "www.jpx.co.jp",
    "www.nasdaq.com",
    "www.tradingview.com",
}
SOURCE_SUFFIXES = {".py", ".js", ".html", ".yml", ".yaml"}
EXCLUDED_PARTS = {".git", "reports", "universes", "vendor"}


def source_files() -> list[Path]:
    return sorted(
        path for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in SOURCE_SUFFIXES
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    findings: list[dict[str, str]] = []
    domains: dict[str, set[str]] = {}
    suspicious = {
        "dynamic_code": re.compile(r"\b(?:eval|exec)\s*\("),
        "shell_pipe": re.compile(r"(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash)\b"),
        "private_key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    }
    url_pattern = re.compile(r"https?://[^\s\"'<>`)]+")

    files = source_files()
    for path in files:
        relative = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8", errors="ignore")
        for url in url_pattern.findall(text):
            domain = (urlparse(url).hostname or "").lower()
            if domain:
                domains.setdefault(domain, set()).add(relative)
                if domain not in ALLOWED_DOMAINS and "${{" not in url:
                    findings.append({"severity": "medium", "type": "unapproved_domain", "file": relative, "detail": domain})
        for finding_type, pattern in suspicious.items():
            if pattern.search(text):
                findings.append({"severity": "high", "type": finding_type, "file": relative, "detail": "suspicious pattern matched"})

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        lower = path.name.lower()
        if lower == ".env" or lower.endswith((".pem", ".key", ".p12", ".pfx")):
            findings.append({"severity": "high", "type": "tracked_secret_file", "file": str(path.relative_to(ROOT)), "detail": lower})

    uses_pattern = re.compile(r"uses:\s*([^\s]+)@([^\s#]+)")
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        for action, ref in uses_pattern.findall(workflow.read_text(encoding="utf-8")):
            if action.startswith("./"):
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                findings.append({"severity": "medium", "type": "unpinned_action", "file": str(workflow.relative_to(ROOT)), "detail": f"{action}@{ref}"})

    vendor_hash = sha256(VENDOR_CHART)
    if vendor_hash != VENDOR_SHA256:
        findings.append({"severity": "high", "type": "vendor_integrity", "file": str(VENDOR_CHART.relative_to(ROOT)), "detail": str(vendor_hash)})

    requirements = []
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        requirements.append({"requirement": value, "exactPin": "==" in value})

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "high": sum(item["severity"] == "high" for item in findings),
            "medium": sum(item["severity"] == "medium" for item in findings),
            "scannedFiles": len(files),
            "vendorIntegrity": vendor_hash == VENDOR_SHA256,
        },
        "allowedDomains": [
            {"domain": domain, "files": sorted(domain_files)} for domain, domain_files in sorted(domains.items())
        ],
        "requirements": requirements,
        "vendor": {
            "name": "lightweight-charts",
            "version": "5.2.0",
            "license": "Apache-2.0",
            "sha256": vendor_hash,
            "expectedSha256": VENDOR_SHA256,
        },
        "findings": findings,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["high"]:
        raise SystemExit("High-severity security audit findings detected")


if __name__ == "__main__":
    main()
