"""Shared helpers for project EPUB post-processing scripts."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "_book"

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

ET.register_namespace("", XHTML_NS)
ET.register_namespace("epub", EPUB_NS)
ET.register_namespace("ncx", NCX_NS)


def qname(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def epub_files_from_env() -> list[Path]:
    output_files = os.environ.get("QUARTO_PROJECT_OUTPUT_FILES", "")
    epubs = [
        PROJECT_ROOT / line.strip()
        for line in output_files.splitlines()
        if line.strip().endswith(".epub")
    ]
    if output_files:
        return epubs
    return sorted(OUTPUT_DIR.glob("*.epub"))


def rewrite_epub(epub_path: Path, patch_entries: Callable[[dict[str, bytes]], bool]) -> bool:
    with zipfile.ZipFile(epub_path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}
        infos = source.infolist()

    if not patch_entries(entries):
        return False

    fd, temp_name = tempfile.mkstemp(suffix=".epub", dir=str(epub_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as target:
            for info in infos:
                out_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                out_info.comment = info.comment
                out_info.extra = info.extra
                out_info.internal_attr = info.internal_attr
                out_info.external_attr = info.external_attr
                out_info.create_system = info.create_system
                out_info.compress_type = (
                    zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
                )
                target.writestr(out_info, entries[info.filename])
        shutil.move(str(temp_path), epub_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return True
