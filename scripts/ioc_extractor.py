#!/usr/bin/env python3
"""Deterministic IOC extractor and automatic defanger for DFIR logs.

Reads raw text/log files, extracts deduplicated IPv4s, URLs, domains, emails,
and cryptographic hashes, defangs network indicators, and flags potential
prompt-injection tampering lines inside untrusted log text.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
URL_RE = re.compile(r"\bhttps?://[^\s'\"<>]+", re.IGNORECASE)
DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9-]{1,63}\.)+(?:[a-zA-Z]{2,24})\b")
EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,24}\b")
SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
SHA1_RE = re.compile(r"\b[a-fA-F0-9]{40}\b")
MD5_RE = re.compile(r"\b[a-fA-F0-9]{32}\b")
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

INJECTION_RE = re.compile(
    r"(ignore\s+previous\s+instructions|disregard\s+all\s+prior|system\s+prompt|classify\s+as\s+benign)",
    re.IGNORECASE,
)

COMMON_NON_DOMAINS = {".exe", ".dll", ".sys", ".log", ".txt", ".json", ".csv", ".py", ".sh", ".ps1", ".elf", ".so"}


def defang_net(value: str) -> str:
    return (
        value.replace("http://", "hxxp://")
        .replace("https://", "hxxps://")
        .replace(".", "[.]")
    )


def valid_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        return False


def extract_iocs(text: str) -> dict:
    ips = sorted({defang_net(ip) for ip in IPV4_RE.findall(text) if valid_ipv4(ip)})
    urls = sorted({defang_net(u.rstrip(".,);")) for u in URL_RE.findall(text)})
    emails = sorted({e.replace("@", "[@]").replace(".", "[.]") for e in EMAIL_RE.findall(text)})

    raw_domains = DOMAIN_RE.findall(text)
    domains = sorted(
        {
            defang_net(d.lower())
            for d in raw_domains
            if not any(d.lower().endswith(ext) for ext in COMMON_NON_DOMAINS)
            and not valid_ipv4(d)
        }
    )

    sha256s = sorted({h.lower() for h in SHA256_RE.findall(text)})
    sha1s = sorted({h.lower() for h in SHA1_RE.findall(text) if not any(h.lower() in s for s in sha256s)})
    md5s = sorted({h.lower() for h in MD5_RE.findall(text) if not any(h.lower() in s for s in sha256s + sha1s)})
    cves = sorted({c.upper() for c in CVE_RE.findall(text)})

    injection_lines = [
        line.strip()[:200]
        for line in text.splitlines()
        if INJECTION_RE.search(line)
    ][:20]

    return {
        "untrusted_data_notice": "Extracted from untrusted logs. Review defanged IOCs before blocking.",
        "counts": {
            "ipv4": len(ips),
            "urls": len(urls),
            "domains": len(domains),
            "emails": len(emails),
            "sha256": len(sha256s),
            "sha1": len(sha1s),
            "md5": len(md5s),
            "cves": len(cves),
            "prompt_injection_flags": len(injection_lines),
        },
        "iocs": {
            "ipv4": ips,
            "urls": urls,
            "domains": domains,
            "emails": emails,
            "sha256": sha256s,
            "sha1": sha1s,
            "md5": md5s,
            "cves": cves,
        },
        "prompt_injection_tampering_flags": injection_lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and defang IOCs from log/text files.")
    parser.add_argument("files", nargs="+", type=Path, help="One or more input text/log files.")
    args = parser.parse_args()

    chunks: list[str] = []
    for file_path in args.files:
        if not file_path.is_file():
            print(json.dumps({"error": f"File not found: {file_path}"}), file=sys.stderr)
            return 1
        chunks.append(file_path.read_text(encoding="utf-8", errors="replace"))

    print(json.dumps(extract_iocs("\n".join(chunks)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
