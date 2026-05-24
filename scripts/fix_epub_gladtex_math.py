#!/usr/bin/env python3
"""Clean up GladTeX-generated math links in EPUB files.

GladTeX can wrap long formula images in anchors pointing at
`_book/gladtex-math/outsourced-descriptions.html`. Pandoc packages the rendered
SVGs into the EPUB but does not include that helper HTML file, so the links are
broken in readers. The rendered math image and alt text are already present, so
this post-render hook unwraps those anchors and keeps the image.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from epub_utils import PROJECT_ROOT, XHTML_NS, epub_files_from_env, qname, rewrite_epub


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
    return rewrite_epub(epub_path, patch_xhtml_entries)


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
