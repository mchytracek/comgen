#!/usr/bin/env python3
"""Legt einen Comic in comics/<nr>-<slug>/ an und macht ihn zum aktiven Comic (Verweis comic → …).

Der erste Comic eines Klons entsteht über scripts/init.sh (macht zusätzlich git + ComfyUI-Adresse),
jeder weitere direkt hiermit – z. B. ein zweiter Band mit denselben Figuren:

  python3 tools/init_comic.py "Wie Rechnungen sich selbst buchen" [--format print-a4|print-us|print-a5-quer|web|social-4x5|social-1x1|social-9x16]
      [--style explainer|ligne-claire|us-comic|manga|graphic-novel] [--purpose explainer|story|product|social] [--lang de]
  python3 tools/init_comic.py "Das geheimnisvolle Quaken" --from 01      # Format, Stil und Figuren von comics/01-…

Wechseln und auflisten: python3 tools/comic.py list | use <nr|ordner>
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata

from _common import COMIC, COMICS, FORMATS, REPO, TEMPLATES, die
from comic import activate, find_comic, migrate_legacy


def slugify(t: str) -> str:
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "comic"


def next_number() -> int:
    nums = [int(m.group(1)) for d in COMICS.glob("*") if (m := re.match(r"(\d+)-", d.name))]
    return max(nums, default=0) + 1


def main():
    styles = json.loads((TEMPLATES / "styles.json").read_text(encoding="utf-8"))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("title")
    ap.add_argument("--slug")
    ap.add_argument("--format", choices=sorted(FORMATS), help="Default print-a4 bzw. wie --from")
    ap.add_argument("--style", choices=sorted(styles), help="Default explainer bzw. wie --from")
    ap.add_argument("--purpose", choices=["explainer", "story", "product", "social"])
    ap.add_argument("--lang")
    ap.add_argument("--from", dest="src", help="vorhandener Comic (Nummer oder Ordner): Format, Stil und Figuren "
                    "samt Fotos und Comic-Referenzen übernehmen")
    a = ap.parse_args()

    migrate_legacy()
    src = find_comic(a.src) if a.src else None
    base = json.loads((src / "comic.json").read_text(encoding="utf-8")) if src else {}
    slug = a.slug or slugify(a.title)
    if any(re.fullmatch(rf"\d+-{re.escape(slug)}", d.name) for d in COMICS.glob("*")):
        die(f"Es gibt schon einen Comic mit slug {slug} in comics/")
    pdir = COMICS / f"{next_number():02d}-{slug}"
    shutil.copytree(TEMPLATES / "project", pdir)
    for d in ("cast", "assets/cast", "assets/panels", "pages", "review", ".work"):
        (pdir / d).mkdir(parents=True, exist_ok=True)

    f = pdir / "comic.json"
    c = json.loads(f.read_text(encoding="utf-8"))
    fmt = a.format or base.get("format") or "print-a4"
    style = a.style or (base.get("style") or {}).get("preset") or "explainer"
    c.update(title=a.title, slug=slug, language=a.lang or base.get("language") or "de", format=fmt,
             purpose=a.purpose or base.get("purpose") or "explainer")
    if base and not a.style:
        c["style"] = base["style"]  # eigene Anpassungen am Stil bleiben erhalten
    else:
        s = styles[style]
        c["style"] = {"preset": style, "imagePrompt": s["imagePrompt"], "castStyle": s["castStyle"],
                      "palette": s["palette"], "fonts": s["fonts"]}
    if "pageNumbers" in base:
        c["pageNumbers"] = base["pageNumbers"]
    if src:
        c["cast"] = base.get("cast", [])
        for d in ("cast", "assets/cast"):
            if (src / d).is_dir():
                shutil.copytree(src / d, pdir / d, dirs_exist_ok=True)
    if fmt.startswith("social"):  # Social: eine Aussage pro Slide, wenige große Panels
        c["pages"][0]["layout"] = [[1], [1, 1]]
        c["pages"][0]["panels"] = c["pages"][0]["panels"][:3]
    f.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    activate(pdir)
    extra = f", {len(c['cast'])} Figuren aus {src.name}" if src else ""
    print(f"✔ {pdir.relative_to(REPO)}/ angelegt: „{a.title}“ ({fmt}, Stil {style}{extra})")
    print(f"  aktiv: {COMIC.name} → {pdir.relative_to(REPO)}")


if __name__ == "__main__":
    main()
