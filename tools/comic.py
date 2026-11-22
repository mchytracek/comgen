#!/usr/bin/env python3
"""Werkzeug für comic/comic.json: validate | show | list | use | formats | styles | layouts.

  python3 tools/comic.py list            # alle Comics in comics/, * = aktiv
  python3 tools/comic.py use 02          # aktiven Comic wechseln (Verweis comic → comics/02-…)
  python3 tools/comic.py validate
  python3 tools/comic.py show            # Seiten, Panels, Figuren, Status der Bilder
  python3 tools/comic.py formats         # Seitenformate (Druck, Web, Social)
  python3 tools/comic.py styles          # Stil-Vorlagen aus templates/styles.json
  python3 tools/comic.py layouts         # benannte Seitenraster
  (alle mit optional --dir <comicordner>)

Seitenraster (`page.layout`): Liste von Zeilen, jede Zeile eine Liste relativer Breiten,
z. B. [[1, 1], [2, 1], [1]] = 2 Panels, dann breit + schmal, dann ein Panel über die volle Breite.
Optional `page.rows` = relative Zeilenhöhen, z. B. [1, 1.5, 1]. Panels in Leserichtung
(zeilenweise, links → rechts). Benannte Raster: siehe `layouts`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

from _common import COMIC, COMICS, FORMATS, REPO, TEMPLATES, all_panels, cast_by_id, die, load_comic, page_geometry, project_dir

NAMED_LAYOUTS: dict[str, list[list[float]]] = {
    "splash": [[1]],
    "2-tier": [[1], [1]],
    "3-tier": [[1], [1], [1]],
    "grid-4": [[1, 1], [1, 1]],
    "grid-6": [[1, 1], [1, 1], [1, 1]],
    "grid-9": [[1, 1, 1], [1, 1, 1], [1, 1, 1]],
    "hero-top": [[1], [1, 1], [1, 1]],
    "hero-bottom": [[1, 1], [1, 1], [1]],
    "classic-5": [[1, 1], [1], [1, 1]],
    "strip-3": [[1, 1, 1]],
    "strip-4": [[1, 1, 1, 1]],
}
BUBBLE_TYPES = {"speech", "thought", "whisper", "shout", "caption", "sfx", "title"}
POSITIONS = {"tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br"}
SHOTS = {"establishing", "wide", "full", "medium", "close", "extreme-close", "over-shoulder", "bird", "worm"}
MAX_WORDS = 30


def resolve_layout(page: dict) -> list[list[float]]:
    lay = page.get("layout", "grid-6")
    if isinstance(lay, str):
        if lay not in NAMED_LAYOUTS:
            die(f"{page.get('id')}: unbekanntes Raster {lay!r} – {', '.join(NAMED_LAYOUTS)}")
        return NAMED_LAYOUTS[lay]
    return lay


def panel_rects(page: dict, geo: dict) -> list[tuple[int, int, int, int]]:
    """Panel-Rechtecke (x, y, w, h) in Ausgabepixeln, in Leserichtung."""
    if page.get("fullBleed"):
        return [(0, 0, geo["W"], geo["H"])]
    rows = resolve_layout(page)
    m, g = geo["margin"], geo["gutter"]
    cw, ch = geo["W"] - 2 * m, geo["H"] - 2 * m
    heights = page.get("rows") or [1] * len(rows)
    if len(heights) != len(rows):
        die(f"{page.get('id')}: rows hat {len(heights)} Werte, layout {len(rows)} Zeilen")
    avail_h = ch - g * (len(rows) - 1)
    rects, y = [], float(m)
    for row, rh in zip(rows, heights):
        h = avail_h * rh / sum(heights)
        avail_w = cw - g * (len(row) - 1)
        x = float(m)
        for cwid in row:
            w = avail_w * cwid / sum(row)
            rects.append((round(x), round(y), round(w), round(h)))
            x += w + g
        y += h + g
    return rects


def validate(c: dict, pdir=None) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    for key in ("title", "slug", "language", "format", "style", "cast", "pages"):
        if key not in c:
            errs.append(f"Pflichtfeld fehlt: {key}")
    if errs:
        return errs, warns
    if c["format"] not in FORMATS:
        errs.append(f"format muss einer von {sorted(FORMATS)} sein")
    if not (c["style"].get("imagePrompt") or "").strip():
        errs.append("style.imagePrompt fehlt")
    cast = cast_by_id(c)
    for m in c["cast"]:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", m.get("id", "")):
            errs.append(f"cast {m.get('id')!r}: id klein, ohne Leerzeichen (z. B. anna, chef-mueller)")
        if not m.get("name"):
            errs.append(f"cast {m.get('id')}: name fehlt")
        if not m.get("look"):
            warns.append(f"cast {m.get('id')}: look fehlt (Aussehen in Worten – hilft dem Bildaufbau)")
        if pdir is not None:
            for k in ("photo", "ref"):
                if m.get(k) and not (pdir / m[k]).exists():
                    errs.append(f"cast {m['id']}: {k} {m[k]} existiert nicht")
    seen: set[str] = set()
    for i, pg in enumerate(c["pages"]):
        pid = pg.get("id", f"#{i}")
        if not re.fullmatch(r"p\d{2,3}", pid):
            errs.append(f"Seite {pid}: id wie p01, p02 …")
        try:
            rows = [[1]] if pg.get("fullBleed") else resolve_layout(pg)
        except SystemExit:
            raise
        cells = sum(len(r) for r in rows)
        panels = pg.get("panels", [])
        if len(panels) != cells:
            errs.append(f"{pid}: Raster hat {cells} Felder, aber {len(panels)} Panels")
        for j, pn in enumerate(panels):
            nid = pn.get("id", "")
            where = f"{pid}/{nid or j}"
            if nid != f"{pid}-{j + 1}":
                errs.append(f"{where}: id muss {pid}-{j + 1} sein (Leserichtung)")
            if nid in seen:
                errs.append(f"{where}: doppelte id")
            seen.add(nid)
            if not (pn.get("prompt") or "").strip() and not (pn.get("assets") or {}).get("image") \
                    and not pn.get("blank"):
                errs.append(f"{where}: prompt fehlt")
            if pn.get("shot") and pn["shot"] not in SHOTS:
                warns.append(f"{where}: shot {pn['shot']!r} unbekannt ({', '.join(sorted(SHOTS))})")
            for who in pn.get("cast", []):
                cid = who if isinstance(who, str) else who.get("id")
                if cid not in cast:
                    errs.append(f"{where}: Figur {cid!r} nicht im cast")
                elif not cast[cid].get("ref"):
                    warns.append(f"{where}: Figur {cid} hat noch keine Comic-Referenz (cast.py add/pick)")
            if len(pn.get("cast", [])) > 1 and any(isinstance(w, str) or not w.get("where")
                                                   for w in pn["cast"]):
                warns.append(f"{where}: mehrere Figuren – je Figur `where` angeben (z. B. \"on the left\")")
            for k, b in enumerate(pn.get("bubbles", [])):
                bw = f"{where} Blase {k + 1}"
                t = b.get("type", "speech")
                if t not in BUBBLE_TYPES:
                    errs.append(f"{bw}: type {t!r} – erlaubt {sorted(BUBBLE_TYPES)}")
                if not (b.get("text") or "").strip():
                    errs.append(f"{bw}: text leer")
                if t in ("speech", "thought", "whisper", "shout") and b.get("who") and b["who"] not in cast \
                        and b["who"] != "off":
                    errs.append(f"{bw}: who {b['who']!r} nicht im cast (oder \"off\" für Stimme aus dem Off)")
                pos = b.get("pos")
                if isinstance(pos, str) and pos not in POSITIONS:
                    errs.append(f"{bw}: pos {pos!r} – {sorted(POSITIONS)} oder {{x, y}}")
                if len((b.get("text") or "").split()) > MAX_WORDS:
                    warns.append(f"{bw}: {len(b['text'].split())} Wörter – Comic-Blasen ≤ {MAX_WORDS}, besser ≤ 20")
            words = sum(len((b.get("text") or "").split()) for b in pn.get("bubbles", []))
            if words > 45:
                warns.append(f"{where}: {words} Wörter im Panel – zu viel Text, Panel teilen")
    return errs, warns


def cmd_validate(a):
    pdir = project_dir(a.project)
    errs, warns = validate(load_comic(pdir), pdir)
    for w in warns:
        print(f"⚠ {w}")
    if errs:
        print("\n".join(f"✖ {e}" for e in errs))
        raise SystemExit(1)
    print(f"✔ {pdir.name}: comic.json gültig")


def cmd_show(a):
    pdir = project_dir(a.project)
    c = load_comic(pdir)
    geo = page_geometry(c["format"])
    print(f"# {c['title']}  [{c.get('status', '?')}]  {c['format']} ({geo['W']}×{geo['H']} px)  "
          f"Stil: {c['style'].get('preset', 'eigen')}\n")
    print("Figuren:")
    for m in c["cast"] or [{"id": "–", "name": "(noch keine)"}]:
        ref = "✔ Comic-Ref" if m.get("ref") else ("Foto" if m.get("photo") else "")
        print(f"  {m['id']:14} {m.get('name', ''):18} {ref:12} {m.get('role', '')}")
    print()
    for pg in c["pages"]:
        rects = panel_rects(pg, geo)
        print(f"{pg['id']}  {pg.get('layout') if not pg.get('fullBleed') else 'fullBleed'}  "
              f"{pg.get('beat', '')}")
        for pn, (x, y, w, h) in zip(pg.get("panels", []), rects):
            cast = ",".join(w_ if isinstance(w_, str) else w_["id"] for w_ in pn.get("cast", []))
            img = "✔" if (pn.get("assets") or {}).get("image") and (pdir / pn["assets"]["image"]).exists() else "·"
            words = sum(len(b.get("text", "").split()) for b in pn.get("bubbles", []))
            print(f"  {img} {pn['id']:7} {w}×{h:<5} {pn.get('shot', ''):13} {cast:16} "
                  f"{len(pn.get('bubbles', []))} Blasen/{words} W  {pn.get('prompt', '')[:50]}")
    n = len(all_panels(c))
    done = sum(1 for _, pn in all_panels(c) if (pn.get("assets") or {}).get("image"))
    print(f"\n{len(c['pages'])} Seiten, {n} Panels, {done} Bilder vorhanden")


def cmd_formats(a):
    for k, f in FORMATS.items():
        g = page_geometry(k)
        print(f"  {k:12} {f['label']:58} → {g['W']}×{g['H']} px")


def cmd_styles(a):
    styles = json.loads((TEMPLATES / "styles.json").read_text(encoding="utf-8"))
    for k, s in styles.items():
        print(f"  {k:16} {s['label']}")


def cmd_layouts(a):
    for k, rows in NAMED_LAYOUTS.items():
        print(f"  {k:12} {rows}")


# ---------------------------------------------------------------------------
# Mehrere Comics pro Repo: comics/<nr>-<slug>/, `comic` ist ein Verweis auf den aktiven.
# ---------------------------------------------------------------------------
def comics() -> list:
    return sorted(d for d in COMICS.glob("*") if (d / "comic.json").exists())


def find_comic(key: str):
    """Comic per Nummer („2“, „02“), Ordnername oder Pfad."""
    p = (REPO / key) if not os.path.isabs(key) else None
    if p and (p / "comic.json").exists():
        return p.resolve()
    hits = [d for d in comics() if d.name == key or d.name.split("-", 1)[0].lstrip("0") == key.lstrip("0")
            or d.name.split("-", 1)[-1] == key]
    if len(hits) != 1:
        die(f"Comic „{key}“ nicht eindeutig gefunden – vorhanden: {', '.join(d.name for d in comics()) or '(keine)'}")
    return hits[0]


def activate(pdir) -> None:
    if COMIC.is_symlink():
        COMIC.unlink()
    elif COMIC.exists():
        die(f"{COMIC} ist ein echter Ordner – erst umziehen (python3 tools/comic.py list zieht ihn nach comics/)")
    COMIC.symlink_to(pdir.relative_to(REPO))


def migrate_legacy() -> None:
    """Alter Klon mit echtem Ordner comic/ → comics/01-<slug>/ + Verweis (git mv, falls versioniert)."""
    if not COMIC.exists() or COMIC.is_symlink():
        return
    slug = (json.loads((COMIC / "comic.json").read_text(encoding="utf-8")).get("slug") or "comic") \
        if (COMIC / "comic.json").exists() else "comic"
    dst = COMICS / f"01-{slug}"
    if dst.exists():
        die(f"Umzug von comic/ nicht möglich: {dst.relative_to(REPO)} existiert schon")
    COMICS.mkdir(exist_ok=True)
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", "comic"],
                             capture_output=True).returncode == 0
    if tracked:
        subprocess.run(["git", "-C", str(REPO), "mv", "comic", str(dst.relative_to(REPO))], check=True)
        if COMIC.exists():  # git mv lässt ignorierte Dateien (Bilder, Fotos) zurück
            for item in list(COMIC.iterdir()):
                target = dst / item.name
                if target.exists() and item.is_dir():
                    for sub in item.rglob("*"):
                        rel = sub.relative_to(item)
                        if sub.is_file() and not (target / rel).exists():
                            (target / rel).parent.mkdir(parents=True, exist_ok=True)
                            sub.rename(target / rel)
                elif not target.exists():
                    item.rename(target)
            import shutil
            shutil.rmtree(COMIC)
        # Fotos echter Personen gehören nicht ins Git (alte Regel ignorierte nur cast/*/photo*)
        subprocess.run(["git", "-C", str(REPO), "rm", "-r", "-q", "--cached", "--ignore-unmatch",
                        str((dst / "cast").relative_to(REPO))], check=True)
    else:
        COMIC.rename(dst)
    activate(dst)
    print(f"✔ comic/ umgezogen nach {dst.relative_to(REPO)}/ (comic ist jetzt ein Verweis darauf)"
          + (" – bitte committen" if tracked else ""))


def cmd_list(a):
    migrate_legacy()
    active = COMIC.resolve() if COMIC.is_symlink() else None
    if not comics():
        print("Noch kein Comic – scripts/init.sh \"<Titel>\" bzw. python3 tools/init_comic.py \"<Titel>\"")
    for d in comics():
        c = load_comic(d)
        mark = "*" if d == active else " "
        print(f"{mark} {d.name:36} {c.get('status', '?'):10} {c['format']:14} {len(c['pages'])} S.  „{c['title']}“")


def cmd_use(a):
    migrate_legacy()
    pdir = find_comic(a.comic)
    activate(pdir)
    print(f"✔ aktiv: comic → {pdir.relative_to(REPO)}  („{load_comic(pdir)['title']}“)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("validate", cmd_validate), ("show", cmd_show), ("formats", cmd_formats),
                     ("styles", cmd_styles), ("layouts", cmd_layouts)):
        p = sub.add_parser(name)
        p.add_argument("--dir", dest="project", help="Comicordner (Default: comic/)")
        p.set_defaults(fn=fn)
    sub.add_parser("list", help="alle Comics, * = aktiv").set_defaults(fn=cmd_list)
    u = sub.add_parser("use", help="aktiven Comic wechseln")
    u.add_argument("comic", help="Nummer (02), Ordner oder slug")
    u.set_defaults(fn=cmd_use)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
