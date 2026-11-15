#!/usr/bin/env python3
"""Erzeugt die Panel-Bilder eines Comics in ComfyUI.

  python3 tools/panels.py                      # alle fehlenden Panels
  python3 tools/panels.py --page p02           # nur eine Seite
  python3 tools/panels.py --only p01-3,p02-1 --force
  python3 tools/panels.py --only p01-2 --reswap  # nur Figuren neu einsetzen (Bildaufbau bleibt)
  python3 tools/panels.py --only p01-2 --swap single  # alte Variante: ein Durchgang pro Figur
  python3 tools/panels.py --dry-run
  python3 tools/panels.py grid p01-2           # Kopie mit Koordinatenraster → review/grid/
  python3 tools/panels.py edit p01-2 "Remove the second girl on the right."    # Bild nachbearbeiten
  python3 tools/panels.py edit p01-2 "Replace the two children with …" --ref robin,nilo

Ablauf je Panel:
  1. Z-Image Turbo erzeugt den Bildaufbau im Seitenverhältnis des Panel-Rahmens
     (Prompt = Einstellung + panel.prompt + Aussehen der Figuren + style.imagePrompt).
  2. Qwen Image 2.1 Edit setzt die Figuren mit Comic-Referenz ein. Standard (`--swap group`):
     ein Durchgang pro Gruppe mit einem Vorlagenblatt (Referenzen nebeneinander):
       a) Tiere (`cast[].animal`)  b) übrige Figuren  c) jede Hauptfigur (`cast[].hero`) allein.
     Das ist deutlich sauberer als ein Durchgang pro Figur (`--swap single`): weniger Rauschen,
     weniger doppelte Figuren. `where` sagt, welche Figur im Bild gemeint ist, `kind` was sie ist.
Ergebnis: comic/assets/panels/<id>.png (+ <id>_base.png, <id>_g0.png …), Pfade in panel.assets.

`edit` bearbeitet ein fertiges Panel per Qwen Edit (Figur entfernen, Requisite ergänzen, Größe
korrigieren). Mit `--ref a,b` bekommt Qwen ein Vorlagenblatt dieser Figuren als <image2> – z. B. um
fremde Personen durch Figuren aus dem Cast zu ersetzen. Das Original bleibt als <id>_pre_edit.png.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from _common import (FORMATS, IMAGE, QEDIT, QEDIT_REF, all_panels, cast_by_id, die, gen_size, load_comic, page_geometry,
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


def noun(m: dict) -> str:
    return m.get("kind") or "person"


def swap_prompt(m: dict, n_members: int) -> str:
    target = f"the {noun(m)} {m['where']}" if m.get("where") else (
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


KEEP = ("Keep everything else in <image1> unchanged: all other characters and animals, the set, the props, "
        "the sky, the lighting, the camera framing and the visual style.")


def swap_groups(members: list[dict]) -> list[list[dict]]:
    """Tiere → übrige Figuren → jede Hauptfigur einzeln (zuletzt = am wenigsten überschrieben)."""
    animals = [m for m in members if m.get("animal")]
    others = [m for m in members if not m.get("animal") and not m.get("hero")]
    heroes = [[m] for m in members if m.get("hero") and not m.get("animal")]
    return [g for g in (animals, others, *heroes) if g]


def group_prompt(ms: list[dict]) -> str:
    def target(m):
        return m.get("where") or f"the {noun(m)}"

    def detail(m):
        return ", ".join(b for b in (m.get("action", ""), m.get("expression", "")) if b)

    if len(ms) == 1:
        m = ms[0]
        d = f"{detail(m)}. " if detail(m) else ""
        return (f"Replace {target(m)} in <image1> with the {noun(m)} from <image2>, so that it becomes exactly that "
                f"character: the same face, hair or fur, body proportions and outfit. {d}"
                f"Keep the pose, position and size from <image1>. {KEEP}")
    lst = ", ".join(f"{k + 1}) a {noun(m)}" for k, m in enumerate(ms))
    maps = "; ".join(f"{target(m)} in <image1> becomes character {k + 1} ({noun(m)})" for k, m in enumerate(ms))
    acts = "; ".join(f"character {k + 1}: {detail(m)}" for k, m in enumerate(ms) if detail(m))
    acts = f"Expressions and actions – {acts}. " if acts else ""
    return (f"<image2> is a character sheet with {len(ms)} characters from left to right: {lst}. Replace the "
            f"matching characters in <image1> with them: {maps}. Each one gets exactly the face, hair or fur, body "
            f"proportions and outfit from <image2>, while keeping the pose, position and size from <image1>. "
            f"{acts}{KEEP}")


def char_sheet(pdir: Path, refs: list[Path], dst: Path) -> Path:
    """Referenzen nebeneinander auf hellgrauem Grund (gleiche Höhe) – <image2> für Qwen Edit."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    ins = [x for r in refs for x in ("-i", str(r))]
    fc = "".join(f"[{k}]scale=-2:900,pad=iw+40:960:20:30:#E8E8E8[v{k}];" for k in range(len(refs)))
    fc += "".join(f"[v{k}]" for k in range(len(refs))) + (f"hstack={len(refs)}" if len(refs) > 1 else "null")
    cp = run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", fc, str(dst)])
    if cp.returncode:
        die(cp.stderr)
    return dst


def image_size(path: Path) -> tuple[int, int]:
    cp = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
              "-of", "json", str(path)])
    if cp.returncode:
        die(cp.stderr)
    st = json.loads(cp.stdout)["streams"][0]
    return st["width"], st["height"]


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
            w, h = gen_size(rw / rh, FORMATS[c["format"]].get("genMP", 1.2))
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
            if a.swap == "group":
                for k, g in enumerate(swap_groups(swappable)):
                    print(f"  Durchgang {k + 1}: {', '.join(m['id'] for m in g)}")
                    sheet = pdir / ".work" / f"sheet_{pid}_{k}.png"
                    if not a.dry_run:
                        char_sheet(pdir, [pdir / m["ref"] for m in g], sheet)
                    img = stage(pdir, cur, f"comgen_{c['slug']}_{pid}_g{k}.png", a.dry_run)
                    ref = stage(pdir, sheet, f"comgen_{c['slug']}_{pid}_sheet{k}.png", a.dry_run)
                    out = run_workflow(pdir, f"{pid}_g{k}", QEDIT_REF, {
                        "prompt": group_prompt(g), "width": w, "height": h, "seed": seed + 7919 * (k + 1),
                        "image": img, "ref": ref, "prefix": f"comgen/{c['slug']}/{pid}_g{k}"},
                        timeout=900, dry=a.dry_run)
                    if out:
                        step = out_dir / f"{pid}_g{k}.png"
                        shutil.copyfile(out, step)
                        cur = step
                swappable = []  # erledigt
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


def cmd_edit(a) -> None:
    pdir = project_dir(a.project)
    c = load_comic(pdir)
    pn = next((p for _, p in all_panels(c) if p["id"] == a.panel), None) or die(f"Panel {a.panel} unbekannt")
    src = pdir / ((pn.get("assets") or {}).get("image") or "")
    if not src.is_file():
        die(f"{a.panel}: noch kein Bild")
    bak = src.with_name(f"{a.panel}_pre_edit.png")
    if not bak.exists():
        shutil.copyfile(src, bak)
    w, h = image_size(src)
    img = stage(pdir, src, f"comgen_{c['slug']}_{a.panel}_edit_src.png")
    params = {"prompt": a.prompt, "width": w, "height": h, "seed": a.seed, "image": img,
              "prefix": f"comgen/{c['slug']}/{a.panel}_edit"}
    spec = QEDIT
    if a.ref:
        cast = cast_by_id(c)
        refs = []
        for cid in a.ref.split(","):
            r = cast.get(cid, {}).get("ref")
            if not r or not (pdir / r).exists():
                die(f"Figur {cid}: keine Referenz")
            refs.append(pdir / r)
        sheet = char_sheet(pdir, refs, pdir / ".work" / f"sheet_{a.panel}_edit.png")
        params["ref"] = stage(pdir, sheet, f"comgen_{c['slug']}_{a.panel}_edit_ref.png")
        spec = QEDIT_REF
    print(f"{a.panel}: {w}×{h}  Qwen Edit{' mit ' + a.ref if a.ref else ''}")
    out = run_workflow(pdir, f"{a.panel}_edit", spec, params, timeout=900)
    shutil.copyfile(out, src)
    print(f"✔ {src.relative_to(pdir)}  (vorher: {bak.relative_to(pdir)})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", dest="project", help="Comicordner (Default: comic/)")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("grid", help="Panel mit Koordinatenraster (für Sprechblasen-Zeiger)")
    g.add_argument("panel")
    e = sub.add_parser("edit", help="fertiges Panel per Qwen Edit nachbearbeiten")
    e.add_argument("panel")
    e.add_argument("prompt", help="Anweisung (englisch, Imperativ); <image1> = Panel, <image2> = Vorlagenblatt")
    e.add_argument("--ref", help="Figuren-IDs für ein Vorlagenblatt als <image2> (robin,nilo)")
    e.add_argument("--seed", type=int, default=1)
    ap.add_argument("--only", help="Panel-IDs, kommagetrennt (p01-2,p03-1)")
    ap.add_argument("--page", help="Seiten-IDs, kommagetrennt (p01,p02)")
    ap.add_argument("--force", action="store_true", help="vorhandene Bilder neu erzeugen")
    ap.add_argument("--reswap", action="store_true", help="nur Figuren neu einsetzen (Bildaufbau bleibt)")
    ap.add_argument("--swap", choices=["group", "single"], default="group",
                    help="Figuren je Gruppe per Vorlagenblatt (Default) oder einzeln einsetzen")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    {"grid": cmd_grid, "edit": cmd_edit}.get(a.cmd, cmd_generate)(a)


if __name__ == "__main__":
    main()
