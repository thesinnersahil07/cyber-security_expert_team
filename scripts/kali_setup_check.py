#!/usr/bin/env python3
"""Verifies defensive Kali Linux DFIR, static analysis, and AppSec tools
used by Cyber Command Hive Apex (strictly defensive / read-only tooling).
"""

from __future__ import annotations

import shutil

CORE_TOOLS = [
    "python3",
    "jq",
    "sha256sum",
    "file",
    "strings",
    "tshark",
    "tcpdump",
    "fls",
    "mmls",
    "exiftool",
    "binwalk",
    "yara",
    "ssdeep",
    "bulk_extractor",
    "radare2",
    "gitleaks",
    "bandit",
    "rg",
]

VOLATILITY_CANDIDATES = ("vol", "vol3", "volatility3")


def main() -> int:
    print("=== Cyber Command Hive Apex: Kali Defensive Tool Check ===")
    missing: list[str] = []

    for tool in CORE_TOOLS:
        found = shutil.which(tool)
        if found:
            print(f"[OK]      {tool:<16} -> {found}")
        else:
            print(f"[MISSING] {tool:<16}")
            missing.append(tool)

    vol_found = next((shutil.which(cmd) for cmd in VOLATILITY_CANDIDATES if shutil.which(cmd)), None)
    if vol_found:
        print(f"[OK]      {'volatility3':<16} -> {vol_found}")
    else:
        print(f"[MISSING] {'volatility3':<16}")
        missing.append("volatility3")

    print()
    if not missing:
        print("All core Kali defensive DFIR tools are installed and ready.")
    else:
        print(f"Missing tools ({len(missing)}): {', '.join(missing)}")
        print("Recommended Kali Linux defensive install command:")
        print("  sudo apt update && sudo apt install -y kali-tools-forensics yara jq gitleaks bandit radare2 volatility3 ripgrep")
        print("Note: If any tool cannot be installed, research_trainer will supply a zero-dependency Python 3 fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
