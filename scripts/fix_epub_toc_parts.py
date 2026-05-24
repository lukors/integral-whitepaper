#!/usr/bin/env python3
"""Preserve Quarto book parts in EPUB navigation files.

Quarto's HTML sidebar keeps the `book.chapters[].part` hierarchy, but the EPUB
writer builds `nav.xhtml`/`toc.ncx` from document headings and flattens those
part labels. This post-render hook patches the EPUB navigation files so reading
apps show the same part grouping as the book config.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUARTO_YML = PROJECT_ROOT / "_quarto.yml"
OUTPUT_DIR = PROJECT_ROOT / "_book"

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

ET.register_namespace("", XHTML_NS)
ET.register_namespace("epub", EPUB_NS)
ET.register_namespace("ncx", NCX_NS)


@dataclass
class Part:
    label: str
    chapters: list[str]


def qname(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def strip_yaml_scalar(value: str) -> str:
    value = value.split(" #", 1)[0].strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def markdown_title(source: str) -> str:
    path = PROJECT_ROOT / source
    if not path.exists():
        return source

    heading_re = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = heading_re.match(line)
        if not match:
            continue
        title = match.group(2)
        title = re.sub(r"\s+\{[^}]*\}\s*$", "", title)
        title = re.sub(r"\s+#+\s*$", "", title)
        title = re.sub(r"[*_`]", "", title)
        title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
        return html.unescape(re.sub(r"\s+", " ", title).strip())

    return source


def match_key(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    text = re.sub(r"^\d+(?:\.\d+)*\s+", "", text)
    return text


def parse_book_parts() -> list[Part]:
    parts: list[Part] = []
    in_chapters = False
    current: Part | None = None

    for raw_line in QUARTO_YML.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not in_chapters:
            if re.match(r"^\s{2}chapters:\s*$", line):
                in_chapters = True
            continue

        if stripped and not line.startswith("    "):
            break
        if not stripped or stripped.startswith("#"):
            continue

        part_match = re.match(r"^\s{4}-\s+part:\s*(.+?)\s*$", line)
        if part_match:
            part_value = strip_yaml_scalar(part_match.group(1))
            current = Part(label=markdown_title(part_value), chapters=[])
            parts.append(current)
            continue

        chapter_match = re.match(r"^\s{6}-\s+(.+?)\s*$", line)
        if current and chapter_match:
            current.chapters.append(strip_yaml_scalar(chapter_match.group(1)))
            continue

        if re.match(r"^\s{4}-\s+", line):
            current = None

    return [part for part in parts if part.chapters]


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


def direct_child(element: ET.Element, tag: str) -> ET.Element | None:
    for child in list(element):
        if child.tag == tag:
            return child
    return None


def navigation_label(element: ET.Element, namespace: str) -> str:
    if namespace == XHTML_NS:
        for child in list(element):
            if child.tag in {qname(XHTML_NS, "a"), qname(XHTML_NS, "span")}:
                return "".join(child.itertext())
        return ""

    label = element.find(f"{qname(NCX_NS, 'navLabel')}/{qname(NCX_NS, 'text')}")
    return label.text if label is not None and label.text else ""


def find_sequence(
    items: list[ET.Element], start: int, keys: list[str], namespace: str
) -> int | None:
    labels = [match_key(navigation_label(item, namespace)) for item in items]
    for idx in range(start, len(items) - len(keys) + 1):
        if labels[idx : idx + len(keys)] == keys:
            return idx
    return None


def child_keys(part: Part) -> list[str]:
    return [match_key(markdown_title(chapter)) for chapter in part.chapters]


def first_href(items: list[ET.Element]) -> str:
    if not items:
        return ""
    anchor = direct_child(items[0], qname(XHTML_NS, "a"))
    return anchor.get("href", "") if anchor is not None else ""


def first_src(items: list[ET.Element]) -> str:
    if not items:
        return ""
    content = direct_child(items[0], qname(NCX_NS, "content"))
    return content.get("src", "") if content is not None else ""


def rebuild_xhtml_nav(root: ET.Element, parts: list[Part]) -> bool:
    toc = None
    for nav in root.iter(qname(XHTML_NS, "nav")):
        if nav.get("id") == "toc" or nav.get(qname(EPUB_NS, "type")) == "toc":
            toc = nav
            break
    if toc is None:
        return False

    toc_ol = direct_child(toc, qname(XHTML_NS, "ol"))
    if toc_ol is None:
        return False

    original_items = [child for child in list(toc_ol) if child.tag == qname(XHTML_NS, "li")]
    new_items: list[ET.Element] = []
    cursor = 0
    changed = False

    for part in parts:
        keys = child_keys(part)
        match_index = find_sequence(original_items, cursor, keys, XHTML_NS)
        if match_index is None:
            continue

        new_items.extend(original_items[cursor:match_index])
        grouped = original_items[match_index : match_index + len(keys)]

        part_li = ET.Element(qname(XHTML_NS, "li"), {qname(EPUB_NS, "type"): "part"})
        part_anchor = ET.SubElement(part_li, qname(XHTML_NS, "a"))
        part_anchor.set("href", first_href(grouped))
        part_anchor.set(qname(EPUB_NS, "type"), "part")
        part_anchor.text = part.label
        nested_ol = ET.SubElement(part_li, qname(XHTML_NS, "ol"), {"class": "toc"})
        for item in grouped:
            nested_ol.append(item)

        new_items.append(part_li)
        cursor = match_index + len(keys)
        changed = True

    if not changed:
        return False

    new_items.extend(original_items[cursor:])
    toc_ol[:] = new_items
    renumber_xhtml_items(toc_ol)
    return True


def renumber_xhtml_items(root_ol: ET.Element) -> None:
    counter = 1

    def walk(ol: ET.Element) -> None:
        nonlocal counter
        for li in [child for child in list(ol) if child.tag == qname(XHTML_NS, "li")]:
            li.set("id", f"toc-li-{counter}")
            counter += 1
            nested = direct_child(li, qname(XHTML_NS, "ol"))
            if nested is not None:
                walk(nested)

    walk(root_ol)


def rebuild_ncx_nav(root: ET.Element, parts: list[Part]) -> bool:
    nav_map = root.find(qname(NCX_NS, "navMap"))
    if nav_map is None:
        return False

    original_items = [
        child for child in list(nav_map) if child.tag == qname(NCX_NS, "navPoint")
    ]
    new_items: list[ET.Element] = []
    cursor = 0
    changed = False

    for part in parts:
        keys = child_keys(part)
        match_index = find_sequence(original_items, cursor, keys, NCX_NS)
        if match_index is None:
            continue

        new_items.extend(original_items[cursor:match_index])
        grouped = original_items[match_index : match_index + len(keys)]

        part_point = ET.Element(qname(NCX_NS, "navPoint"), {"class": "part"})
        label = ET.SubElement(part_point, qname(NCX_NS, "navLabel"))
        text = ET.SubElement(label, qname(NCX_NS, "text"))
        text.text = part.label
        ET.SubElement(part_point, qname(NCX_NS, "content"), {"src": first_src(grouped)})
        for item in grouped:
            part_point.append(item)

        new_items.append(part_point)
        cursor = match_index + len(keys)
        changed = True

    if not changed:
        return False

    new_items.extend(original_items[cursor:])
    nav_map[:] = new_items
    renumber_ncx_items(nav_map)
    return True


def renumber_ncx_items(nav_map: ET.Element) -> None:
    counter = 1

    def walk(parent: ET.Element) -> None:
        nonlocal counter
        for point in [
            child for child in list(parent) if child.tag == qname(NCX_NS, "navPoint")
        ]:
            point.set("id", f"navPoint-{counter}")
            point.set("playOrder", str(counter))
            counter += 1
            walk(point)

    walk(nav_map)


def patch_epub(epub_path: Path, parts: list[Part]) -> bool:
    with zipfile.ZipFile(epub_path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}
        infos = source.infolist()

    nav_path = "EPUB/nav.xhtml"
    ncx_path = "EPUB/toc.ncx"
    if nav_path not in entries or ncx_path not in entries:
        return False

    nav_root = ET.fromstring(entries[nav_path])
    ncx_root = ET.fromstring(entries[ncx_path])
    nav_changed = rebuild_xhtml_nav(nav_root, parts)
    ncx_changed = rebuild_ncx_nav(ncx_root, parts)

    if not nav_changed and not ncx_changed:
        return False

    if nav_changed:
        entries[nav_path] = ET.tostring(
            nav_root, encoding="utf-8", xml_declaration=True, short_empty_elements=False
        )
    if ncx_changed:
        entries[ncx_path] = ET.tostring(
            ncx_root, encoding="utf-8", xml_declaration=True, short_empty_elements=False
        )

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
    parts = parse_book_parts()
    if not parts:
        return 0

    patched = []
    for epub_path in epub_files_from_env():
        if epub_path.exists() and patch_epub(epub_path, parts):
            patched.append(epub_path.relative_to(PROJECT_ROOT))

    if patched:
        print("Patched EPUB part navigation: " + ", ".join(str(path) for path in patched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
