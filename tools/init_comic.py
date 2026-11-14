#!/usr/bin/env python3
"""Legt in einem frisch geklonten Repo den Comicordner comic/ an.

Normalerweise über scripts/init.sh aufgerufen (macht zusätzlich git + ComfyUI-Adresse).

  python3 tools/init_comic.py "Wie Rechnungen sich selbst buchen" [--format print-a4|print-us|web|social-4x5|social-1x1|social-9x16]
      [--style explainer|ligne-claire|us-comic|manga|graphic-novel] [--purpose explainer|story|product|social] [--lang de]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata

from _common import COMIC, FORMATS, REPO, TEMPLATES, die


def slugify(t: str) -> str:
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "comic"


def main():
    styles = json.loads((TEMPLATES / "styles.json").read_text(encoding="utf-8"))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("title")
    ap.add_argument("--slug")
    ap.add_argument("--format", default="print-a4", choices=sorted(FORMATS))
    ap.add_argument("--style", default="explainer", choices=sorted(styles))
    ap.add_argument("--purpose", default="explainer", choices=["explainer", "story", "product", "social"])
    ap.add_argument("--lang", default="de")
    a = ap.parse_args()

    if COMIC.exists():
        die(f"{COMIC.relative_to(REPO)}/ existiert bereits – dieses Repo ist schon initialisiert")
    shutil.copytree(TEMPLATES / "project", COMIC)
    for d in ("cast", "assets/cast", "assets/panels", "pages", "review", ".work"):
        (COMIC / d).mkdir(parents=True, exist_ok=True)

    f = COMIC / "comic.json"
    c = json.loads(f.read_text(encoding="utf-8"))
    s = styles[a.style]
    c.update(title=a.title, slug=a.slug or slugify(a.title), language=a.lang, format=a.format, purpose=a.purpose)
    c["style"] = {"preset": a.style, "imagePrompt": s["imagePrompt"], "castStyle": s["castStyle"],
                  "palette": s["palette"], "fonts": s["fonts"]}
    if a.format.startswith("social"):  # Social: eine Aussage pro Slide, wenige große Panels
        c["pages"][0]["layout"] = [[1], [1, 1]]
        c["pages"][0]["panels"] = c["pages"][0]["panels"][:3]
    f.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✔ comic/ angelegt: „{a.title}“ (slug {c['slug']}, {a.format}, Stil {a.style})")


if __name__ == "__main__":
    main()
