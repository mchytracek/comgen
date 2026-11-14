#!/usr/bin/env python3
"""Figuren (Cast) eines Comics: Foto hochladen → automatisch im Comicstil rendern → Referenz wählen.

  python3 tools/cast.py add anna ~/Desktop/anna.jpg --name "Anna" --role "Buchhalterin, Heldin"
        # kopiert das Foto nach comic/cast/anna/, rendert 3 Comic-Varianten und übernimmt
        # Variante 1 vorläufig als Referenz (später mit `pick` ändern)
  python3 tools/cast.py add max --name "Max" --look "lanky man in his 30s, curly brown hair, round glasses, green hoodie"
        # ohne Foto: Figur aus der Beschreibung (Z-Image)
  python3 tools/cast.py render anna --seeds 4,5,6 [--waist-up] [--prompt "…"]   # weitere Varianten
  python3 tools/cast.py pick anna 5          # Variante als Referenz → comic/assets/cast/anna.png
  python3 tools/cast.py list

Vergleichsbild je Figur: comic/review/cast/<id>/grid.png (Foto links, dann die Varianten).
Die Story und alle Panels beziehen sich auf die id (`panel.cast`, `bubble.who`).
Fotos von Personen nur mit deren Einverständnis verwenden – sie bleiben lokal (git-ignoriert).
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from _common import (IMAGE, QEDIT, cast_by_id, die, load_comic, patch_comic, project_dir, run,
                     run_workflow, stage)

PHOTO_PROMPT = (
    "Turn the person in this photo into a {framing} comic character in this visual style: {style}. "
    "Stylize the face the way this style does, but keep the person clearly recognizable: the same face shape, "
    "the same hairstyle and hair colour, the same facial hair, the same eyes, eyebrows and smile, the same body shape "
    "and the same clothing and colours. {pose} Arms relaxed, hands empty – leave out phones, cups, bags "
    "and other objects the person is holding. Plain light grey backdrop, no text."
)
INVENT_PROMPT = (
    "Character design sheet of a single {framing} comic character: {look}. {pose} "
    "Arms relaxed, hands empty. Plain light grey backdrop, no text, no letters. Style: {style}"
)
FRAMING = {
    "full": ("full-body", "The character stands facing the camera, the whole figure visible from head to shoes.",
             (832, 1216)),
    "waist": ("waist-up", "The character faces the camera, framed from the waist up.", (1024, 1024)),
}


def _style(c: dict) -> str:
    return (c["style"].get("castStyle") or c["style"].get("imagePrompt") or "").strip().rstrip(".")


def render(pdir: Path, cid: str, seeds: list[int], waist: bool, prompt: str | None, dry: bool) -> list[Path]:
    c = load_comic(pdir)
    m = cast_by_id(c).get(cid) or die(f"Figur {cid!r} nicht im cast – erst `cast.py add`")
    framing, pose, (w, h) = FRAMING["waist" if waist else "full"]
    out_dir = pdir / "review" / "cast" / cid
    out_dir.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    if m.get("photo"):
        photo = pdir / m["photo"]
        # kleine Handyfotos hochskalieren – Qwen Edit ignoriert die Anweisung sonst gern
        big = pdir / ".work" / f"cast_{cid}_src.png"
        big.parent.mkdir(exist_ok=True)
        cp = run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(photo), "-vf",
                  "scale='if(lt(ih,1024),-2,iw)':'if(lt(ih,1024),1024,ih)':flags=lanczos", str(big)])
        if cp.returncode:
            die(f"ffmpeg: {cp.stderr.strip()}")
        name = stage(pdir, big, f"comgen_{c['slug']}_{cid}_src.png", dry)
        text = prompt or PHOTO_PROMPT.format(framing=framing, style=_style(c), pose=pose)
        if m.get("look") and not prompt:
            text += f" Keep these details: {m['look']}."
        for seed in seeds:
            print(f"{cid}: Comic-Variante Seed {seed} (Qwen Image Edit, Foto → Stil)")
            out = run_workflow(pdir, f"cast_{cid}_{seed}", QEDIT, {
                "prompt": text, "width": w, "height": h, "seed": seed, "image": name,
                "prefix": f"comgen/{c['slug']}/cast_{cid}_{seed}"}, dry=dry)
            if out:
                made.append(_keep(out, out_dir / f"v{seed}.png"))
    else:
        if not m.get("look"):
            die(f"{cid}: weder Foto noch look – `cast.py add {cid} <foto>` oder --look \"…\" angeben")
        text = prompt or INVENT_PROMPT.format(framing=framing, look=m["look"], pose=pose, style=_style(c))
        for seed in seeds:
            print(f"{cid}: Comic-Variante Seed {seed} (Z-Image, aus Beschreibung)")
            out = run_workflow(pdir, f"cast_{cid}_{seed}", IMAGE, {
                "prompt": text, "width": w, "height": h, "seed": seed,
                "prefix": f"comgen/{c['slug']}/cast_{cid}_{seed}"}, dry=dry)
            if out:
                made.append(_keep(out, out_dir / f"v{seed}.png"))
    if made:
        _grid(pdir, m, made, out_dir / "grid.png")
    return made


def _keep(src: Path, dst: Path) -> Path:
    shutil.copyfile(src, dst)
    return dst


def _grid(pdir: Path, m: dict, variants: list[Path], dst: Path) -> None:
    imgs = ([pdir / m["photo"]] if m.get("photo") else []) + variants
    inputs = [x for p in imgs for x in ("-i", str(p))]
    n = len(imgs)
    chains = ";".join(f"[{i}]scale=-2:560,pad=iw+20:600:10:20:white[v{i}]" for i in range(n))
    cp = run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
              f"{chains};{''.join(f'[v{i}]' for i in range(n))}hstack=inputs={n}", str(dst)])
    if cp.returncode == 0:
        label = "Foto, dann " if m.get("photo") else ""
        print(f"✔ Vergleich ({label}Varianten {', '.join(p.stem for p in variants)}): {dst.relative_to(pdir)}")


def pick(pdir: Path, cid: str, seed: int, provisional: bool = False) -> None:
    src = pdir / "review" / "cast" / cid / f"v{seed}.png"
    if not src.is_file():
        die(f"{src.relative_to(pdir)} fehlt – erst `cast.py render {cid} --seeds {seed}`")
    dst = pdir / "assets" / "cast" / f"{cid}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

    def apply(c: dict) -> None:
        m = cast_by_id(c)[cid]
        m["ref"] = f"assets/cast/{cid}.png"
        m["refSeed"] = seed
        if provisional:
            m["refProvisional"] = True
        else:
            m.pop("refProvisional", None)
    patch_comic(pdir, apply)
    tag = " (vorläufig – Varianten ansehen und ggf. `cast.py pick` mit anderem Seed)" if provisional else ""
    print(f"✔ {cid}: Referenz = assets/cast/{cid}.png (Variante {seed}){tag}")
    stale = [pn["id"] for pg in load_comic(pdir)["pages"] for pn in pg.get("panels", [])
             if (pn.get("assets") or {}).get("image") and any(
                 (w if isinstance(w, str) else w.get("id")) == cid for w in pn.get("cast", []))]
    if stale:
        print(f"  Panels mit {cid} neu erzeugen: python3 tools/panels.py --only {','.join(stale)} --reswap")


def cmd_add(pdir: Path, a) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]*", a.id):
        die("id klein und ohne Leerzeichen, z. B. anna oder chef-mueller")
    c = load_comic(pdir)
    if a.id in cast_by_id(c) and not a.update:
        die(f"Figur {a.id} existiert schon – `cast.py render {a.id}` für neue Varianten oder --update")
    entry = {"id": a.id, "name": a.name or a.id.capitalize()}
    if a.role:
        entry["role"] = a.role
    if a.look:
        entry["look"] = a.look
    if a.photo:
        src = Path(a.photo).expanduser()
        if not src.is_file():
            die(f"Foto nicht gefunden: {src}")
        dst = pdir / "cast" / a.id / f"photo{src.suffix.lower() or '.jpg'}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        entry["photo"] = str(dst.relative_to(pdir))

    def apply(cc: dict) -> None:
        cur = cast_by_id(cc).get(a.id)
        if cur:
            cur.update(entry)
        else:
            cc["cast"].append(entry)
    patch_comic(pdir, apply)
    print(f"✔ Figur {a.id} ({entry['name']}) im cast" + (f", Foto {entry['photo']}" if a.photo else ""))
    if a.no_render:
        return
    seeds = [int(x) for x in a.seeds.split(",")]
    made = render(pdir, a.id, seeds, a.waist_up, None, a.dry_run)
    if made:
        pick(pdir, a.id, seeds[0], provisional=True)


def cmd_render(pdir: Path, a) -> None:
    render(pdir, a.id, [int(x) for x in a.seeds.split(",")], a.waist_up, a.prompt, a.dry_run)
    print(f"  → ansehen, dann: python3 tools/cast.py pick {a.id} <seed>")


def cmd_pick(pdir: Path, a) -> None:
    pick(pdir, a.id, int(a.seed))


def cmd_list(pdir: Path, a) -> None:
    c = load_comic(pdir)
    if not c["cast"]:
        print("Noch keine Figuren – python3 tools/cast.py add <id> <foto> --name …")
    for m in c["cast"]:
        state = ("Referenz (vorläufig)" if m.get("refProvisional") else "Referenz ✔") if m.get("ref") \
            else "keine Referenz"
        src = "Foto" if m.get("photo") else "Beschreibung"
        print(f"  {m['id']:14} {m['name']:18} {src:12} {state:22} {m.get('role', '')}")
        if m.get("look"):
            print(f"  {'':14} look: {m['look']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", dest="project", help="Comicordner (Default: comic/)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="Figur anlegen (mit Foto oder Beschreibung) und rendern")
    p.add_argument("id")
    p.add_argument("photo", nargs="?")
    p.add_argument("--name")
    p.add_argument("--role")
    p.add_argument("--look", help="Aussehen in Worten (englisch), z. B. 'short red hair, green jacket'")
    p.add_argument("--seeds", default="1,2,3")
    p.add_argument("--waist-up", action="store_true")
    p.add_argument("--no-render", action="store_true", help="nur eintragen, nicht rendern")
    p.add_argument("--update", action="store_true", help="bestehende Figur aktualisieren")
    p.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("render", help="(weitere) Comic-Varianten einer Figur")
    r.add_argument("id")
    r.add_argument("--seeds", default="4,5,6")
    r.add_argument("--waist-up", action="store_true")
    r.add_argument("--prompt")
    r.add_argument("--dry-run", action="store_true")
    k = sub.add_parser("pick", help="Variante als Referenz übernehmen")
    k.add_argument("id")
    k.add_argument("seed")
    sub.add_parser("list")
    a = ap.parse_args()
    pdir = project_dir(a.project)
    {"add": cmd_add, "render": cmd_render, "pick": cmd_pick, "list": cmd_list}[a.cmd](pdir, a)


if __name__ == "__main__":
    main()
