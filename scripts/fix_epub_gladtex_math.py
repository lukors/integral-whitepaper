#!/usr/bin/env python3
"""Clean up GladTeX-generated math links in EPUB files.

GladTeX can wrap long formula images in anchors pointing at
`_book/gladtex-math/outsourced-descriptions.html`. Pandoc packages the rendered
SVGs into the EPUB but does not include that helper HTML file, so the links are
broken in readers. The rendered math image and alt text are already present, so
this post-render hook unwraps those anchors and keeps the image.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "_book"

XHTML_NS = "http://www.w3.org/1999/xhtml"

ET.register_namespace("", XHTML_NS)


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


def unwrap_gladtex_links(parent: ET.Element) -> bool:
    changed = False
    for child in list(parent):
        if unwrap_gladtex_links(child):
            changed = True

    new_children: list[ET.Element] = []
    for child in list(parent):
        href = child.get("href", "")
        if child.tag == qname(XHTML_NS, "a") and "outsourced-descriptions.html" in href:
            replacements = list(child)
            if replacements:
                if child.tail:
                    replacements[-1].tail = (replacements[-1].tail or "") + child.tail
                new_children.extend(replacements)
                changed = True
                continue

        new_children.append(child)

    if changed:
        parent[:] = new_children

    return changed


def patch_xhtml_entries(entries: dict[str, bytes]) -> bool:
    changed = False
    for path, data in list(entries.items()):
        if not path.startswith("EPUB/text/") or not path.endswith(".xhtml"):
            continue

        root = ET.fromstring(data)
        if unwrap_gladtex_links(root):
            entries[path] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
                short_empty_elements=True,
            )
            changed = True

    return changed


def patch_epub(epub_path: Path) -> bool:
    with zipfile.ZipFile(epub_path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}
        infos = source.infolist()

    if not patch_xhtml_entries(entries):
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


def main() -> int:
    patched = []
    for epub_path in epub_files_from_env():
        if epub_path.exists() and patch_epub(epub_path):
            patched.append(epub_path.relative_to(PROJECT_ROOT))

    if patched:
        print("Patched EPUB GladTeX math links: " + ", ".join(str(path) for path in patched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
