"""Build a reproducible .mtp archive using the Python standard library."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MEMBERS = ("manifest.yaml", "README.md", "CHANGELOG.md", "LICENSE", "requirements.txt", "src/anysearch_plugin.py")


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name in MEMBERS:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            package.writestr(info, (ROOT / name).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the official AnySearch plugin package")
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "dist" / "maintune-plugin-anysearch-0.1.0.mtp")
    build(parser.parse_args().output)
