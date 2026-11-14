#!/usr/bin/env python3
"""Erzeugt die Panel-Bilder eines Comics in ComfyUI.

  python3 tools/panels.py                      # alle fehlenden Panels
  python3 tools/panels.py --page p02           # nur eine Seite
  python3 tools/panels.py --only p01-3,p02-1 --force
  python3 tools/panels.py --only p01-2 --reswap  # nur Figuren neu einsetzen (Bildaufbau bleibt)
  python3 tools/panels.py --dry-run
  python3 tools/panels.py grid p01-2           # Kopie mit Koordinatenraster → review/grid/

Ablauf je Panel:
  1. Z-Image Turbo erzeugt den Bildaufbau im Seitenverhältnis des Panel-Rahmens
     (Prompt = Einstellung + panel.prompt + Aussehen der Figuren + style.imagePrompt).
  2. Für jede Figur in `panel.cast` mit Comic-Referenz setzt Qwen Image 2.1 Edit die Figur ein
     (ein Durchgang pro Figur; bei mehreren Figuren sagt `where`, welche gemeint ist).
Ergebnis: comic/assets/panels/<id>.png (+ <id>_base.png), Pfade in panel.assets.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from _common import (IMAGE, QEDIT_REF, all_panels, cast_by_id, die, gen_size, load_comic, page_geometry,
                     patch_panel, project_dir, run, run_workflow, select, stage)
from comic import panel_rects, validate

SHOT = {
    "establishing": "Establishing shot, wide view of the whole location.",
    "wide": "Wide shot, the characters small within the setting.",
    "full": "Full shot, the whole figures visible from head to feet.",
    "medium": "Medium shot, characters framed from the waist up.",
    "close": "Close-up on the face and shoulders.",
    "extreme-close": "Extreme close-up on a detail.",
    "over-shoulder": "Over-the-shoulder shot.",
    "bird": "High-angle bird's-eye view looking down.",
    "worm": "Low-angle worm's-eye view looking up.",
}


def _members(pn: dict, cast: dict) -> list[dict]:
    out = []
    for w in pn.get("cast", []):
        e = {"id": w} if isinstance(w, str) else dict(w)
        e.update({k: v for k, v in cast.get(e["id"], {}).items() if k not in e})
        out.append(e)
    return out


def base_prompt(c: dict, pn: dict, members: list[dict]) -> str:
    parts = [SHOT.get(pn.get("shot", ""), ""), pn.get("prompt", "").strip().rstrip(".") + "."]
    if members:
        descr = []
        for m in members:
            look = m.get("look") or "a person"
            bits = [m.get("where", ""), look, m.get("action", ""), m.get("expression", "")]
            descr.append(", ".join(b for b in bits if b))
        parts.append("Characters: " + "; ".join(descr) + ".")
    parts.append(c["style"]["imagePrompt"].strip())
    return " ".join(p for p in parts if p)


def swap_prompt(m: dict, n_members: int) -> str:
    target = f"the person {m['where']}" if m.get("where") else (
        "the main character" if n_members == 1 else "the matching character")
    wear = m.get("wear") or "The character wears the outfit of <image2>."
    action = m.get("action") or ""
    expr = f"Facial expression: {m['expression']}." if m.get("expression") else ""
    keep = "pose, position and size" if action else "pose, gesture, facial expression, position and size"
    return (f"Replace {target} in <image1> with the character from <image2>, so that it becomes exactly that "
            "character: the same face, the same hairstyle and facial hair, the same body shape. "
            f"{wear} {action} {expr} Keep the {keep} from <image1>, and keep everything else in <image1> "
            "unchanged: the set, the props, all other people, the lighting, the camera framing and the "
            "visual style.").replace("  ", " ").replace("  ", " ")


def default_seed(pid: str) -> int:
    page, idx = pid[1:].split("-")
    return int(page) * 100 + int(idx)


def cmd_generate(a) -> None:
    pdir = project_dir(a.project)
    c = load_comic(pdir)
    errs, _ = validate(c, pdir)
    if errs:
        die("comic.json ungültig – erst `python3 tools/comic.py validate`:\n" + "\n".join(errs))
    geo = page_geometry(c["format"])
    ids = [pn["id"] for _, pn in all_panels(c)]
    only = select(ids, a.only)
    pages = select([pg["id"] for pg in c["pages"]], a.page)
    out_dir = pdir / "assets" / "panels"
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = 0
    for pg in c["pages"]:
        if pages and pg["id"] not in pages:
            continue
        for pn, (_, _, rw, rh) in zip(pg["panels"], panel_rects(pg, geo)):
            pid = pn["id"]
            if only and pid not in only:
                continue
            assets = pn.get("assets") or {}
            final = pdir / assets["image"] if assets.get("image") else None
            if final and final.exists() and not (a.force or a.reswap):
                continue
            todo += 1
            c = load_comic(pdir)  # frisch – Änderungen während langer Läufe bleiben erhalten
            pn = next(p for _, p in all_panels(c) if p["id"] == pid)
            members = [m for m in _members(pn, cast_by_id(c))]
            swappable = [m for m in members if m.get("ref") and (pdir / m["ref"]).exists()]
            w, h = gen_size(rw / rh)
            seed = pn.get("seed", default_seed(pid))
            base = out_dir / f"{pid}_base.png"
            print(f"{pid}: {w}×{h}  Figuren: {', '.join(m['id'] for m in members) or '–'}")
            if a.reswap and base.exists():
                cur = base
            else:
                out = run_workflow(pdir, f"{pid}_base", IMAGE, {
                    "prompt": base_prompt(c, pn, members), "width": w, "height": h, "seed": seed,
                    "prefix": f"comgen/{c['slug']}/{pid}_base"}, timeout=600, dry=a.dry_run)
                if a.dry_run:
                    cur = base
                else:
                    shutil.copyfile(out, base)
                    cur = base
            for k, m in enumerate(swappable):
                img = stage(pdir, cur, f"comgen_{c['slug']}_{pid}_s{k}.png", a.dry_run)
                ref = stage(pdir, pdir / m["ref"], f"comgen_{c['slug']}_cast_{m['id']}.png", a.dry_run)
                print(f"  Figur {m['id']} einsetzen (Qwen Image Edit)")
                out = run_workflow(pdir, f"{pid}_swap_{m['id']}", QEDIT_REF, {
                    "prompt": swap_prompt(m, len(members)), "width": w, "height": h, "seed": seed,
                    "image": img, "ref": ref, "prefix": f"comgen/{c['slug']}/{pid}_{m['id']}"},
                    timeout=900, dry=a.dry_run)
                if out:
                    step = out_dir / f"{pid}_s{k}.png"
                    shutil.copyfile(out, step)
                    cur = step
            if a.dry_run:
                continue
            dst = out_dir / f"{pid}.png"
            shutil.copyfile(cur, dst)
            rel = lambda p: str(p.relative_to(pdir))  # noqa: E731
            patch_panel(pdir, pid, lambda p: p.setdefault("assets", {}).update(
                image=rel(dst), base=rel(base)))
            print(f"  → {rel(dst)}")
    if not todo:
        print("Nichts zu tun – alle Panels haben Bilder (--force / --reswap zum Erneuern).")


def cmd_grid(a) -> None:
    pdir = project_dir(a.project)
    c = load_comic(pdir)
    pn = next((p for _, p in all_panels(c) if p["id"] == a.panel), None) or die(f"Panel {a.panel} unbekannt")
    src = pdir / ((pn.get("assets") or {}).get("image") or "")
    if not src.is_file():
        die(f"{a.panel}: noch kein Bild")
    dst = pdir / "review" / "grid" / f"{a.panel}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = ("drawgrid=w=iw/20:h=ih/20:t=1:c=magenta@0.35,drawgrid=w=iw/10:h=ih/10:t=2:c=magenta@0.8,"
          "drawgrid=w=iw/2:h=ih/2:t=5:c=red@0.9")
    cp = run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-frames:v", "1", str(dst)])
    if cp.returncode:
        die(cp.stderr)
    print(f"✔ {dst.relative_to(pdir)}  (dünn 5 %, mittel 10 %, dick rot 50 %; Koordinaten = Anteile 0–1)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", dest="project", help="Comicordner (Default: comic/)")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("grid", help="Panel mit Koordinatenraster (für Sprechblasen-Zeiger)")
    g.add_argument("panel")
    ap.add_argument("--only", help="Panel-IDs, kommagetrennt (p01-2,p03-1)")
    ap.add_argument("--page", help="Seiten-IDs, kommagetrennt (p01,p02)")
    ap.add_argument("--force", action="store_true", help="vorhandene Bilder neu erzeugen")
    ap.add_argument("--reswap", action="store_true", help="nur Figuren neu einsetzen (Bildaufbau bleibt)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cmd_grid(a) if a.cmd == "grid" else cmd_generate(a)


if __name__ == "__main__":
    main()
