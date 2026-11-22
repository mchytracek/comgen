#!/usr/bin/env python3
"""Setzt die Comic-Seiten: Panels, Sprechblasen, Erzählerkästen, Soundwörter → PNG/PDF.

  python3 tools/layout.py                  # alle Seiten → comic/pages/<id>.png (+ PDF bei Druckformaten)
  python3 tools/layout.py --page p01,p02   # nur diese PNGs; das PDF enthält immer alle Seiten
  python3 tools/layout.py --pdf            # PDF auch für Web/Social erzeugen
  python3 tools/layout.py --no-png         # nur PDF
  python3 tools/layout.py sheet            # Übersicht aller Seiten → comic/review/sheet.png

Funktioniert auch ohne Panel-Bilder (graue Platzhalter mit Prompt) – als Rohlayout,
um Seitenaufteilung und Textmengen vor der Bilderzeugung zu prüfen.

Lettering kommt immer aus dem Code, nie aus dem Bildmodell. Blasen (panel.bubbles):
  {"type": "speech|thought|whisper|shout|caption|sfx", "who": "<cast-id>|off", "text": "…",
   "pos": "tl|tc|tr|ml|mc|mr|bl|bc|br" oder {"x": 0.05, "y": 0.1, "w": 0.4},
   "tail": {"x": 0.62, "y": 0.55} | "none"}
  pos {x, y} = linke obere Ecke der Blase, w = maximale Breite – alles Anteile (0–1) des Panels.
  "title": großer Cover-Schriftzug (Font wie sfx, Kontur + Schatten), "color" = Füllfarbe,
  pos.w = Breite, Text zentriert.
  Panel-Felder für Sonderseiten (Figurenvorstellung, Rückseite): "fit": "contain" (Bild ganz zeigen),
  "pad": {"t","r","b","l"} (Bildfläche einrücken, Anteile), "bg": Hintergrundfarbe, "frame": false
  (kein Rahmen), "blank": true (Feld ohne Bild, z. B. für Überschriften).
  tail = Mund der sprechenden Figur (Anteil des Panels) – der Zeiger endet kurz davor;
  ohne Angabe zeigt er nach unten.
Gerendert wird mit einem Headless-Chrome (eigenes Profil in comic/.work/chrome, das laufende
Chrome bleibt unberührt). Anderer Browser: COMGEN_CHROME=/pfad/zum/binary.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

from _common import REPO, chrome, die, load_comic, page_geometry, project_dir, run, select
from comic import panel_rects, validate

DEFAULT_POS = {"caption": ["tl", "tr", "bl"], "sfx": ["tc", "mc"],
               "other": ["tl", "tr", "bl", "br", "tc", "bc", "ml", "mr"]}
POS_CSS = {
    "tl": "left:4%;top:4%", "tc": "left:50%;top:4%;--tx:-50%", "tr": "right:4%;top:4%",
    "ml": "left:4%;top:50%;--ty:-50%", "mc": "left:50%;top:50%;--tx:-50%;--ty:-50%",
    "mr": "right:4%;top:50%;--ty:-50%",
    "bl": "left:4%;bottom:4%", "bc": "left:50%;bottom:4%;--tx:-50%", "br": "right:4%;bottom:4%",
}
FONT_FILES = {  # fonts/ (OFL, von scripts/setup.sh geladen) – Fallback Comic Sans MS
    ("Comic Neue", 400): "ComicNeue-Regular.ttf", ("Comic Neue", 700): "ComicNeue-Bold.ttf",
    ("Bangers", 400): "Bangers-Regular.ttf",
}

CSS = r"""
%(fontfaces)s
:root { --paper:%(paper)s; --ink:%(ink)s; --cap:%(caption)s; --accent:%(accent)s; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #777; }
.page { position: relative; width: %(W)dpx; height: %(H)dpx; background: var(--paper); overflow: hidden;
        container-type: size; font-family: '%(dialogue)s', 'Comic Sans MS', 'Chalkboard SE', sans-serif; }
.panel { position: absolute; }
.art { position: absolute; inset: 0; overflow: hidden; background: #d9d9d9;
       border: %(border).3fcqw solid var(--ink); }
.art img { width: 100%%; height: 100%%; object-fit: cover; display: block; }
.ph { position: absolute; inset: 0; padding: 4%%; color: #555; font: 1.1cqw/1.3 Helvetica, Arial, sans-serif; }
.ph b { display: block; font-size: 1.6cqw; margin-bottom: .5em; color: #333; }
.fullbleed .art { border: 0; }
svg.tails { position: absolute; inset: 0; width: 100%%; height: 100%%; overflow: visible; pointer-events: none; }
svg.under { z-index: 1; } svg.over { z-index: 3; }
.b { position: absolute; z-index: 2; max-width: min(92%%, max(var(--mw, 46%%), 10em)); hyphens: manual; font-size: calc(%(letter).2fcqw * var(--s, 1)); line-height: 1.18;
     font-weight: 700; color: var(--ink); text-align: center; transform: translate(var(--tx, 0), var(--ty, 0));
     %(upper)s }
.b.speech, .b.thought, .b.whisper, .b.shout { background: var(--paper); border: %(stroke).3fcqw solid var(--ink);
     border-radius: 50%%; padding: 1.0em 1.35em; }
.b.whisper { border-style: dashed; font-weight: 400; }
.b.shout { border-width: %(stroke2).3fcqw; border-radius: 38%%; text-transform: uppercase; font-size: calc(%(letter2).2fcqw * var(--s, 1)); }
.b.thought { border-radius: 50%% / 46%%; font-weight: 400; font-style: italic; }
.b.caption { background: var(--cap); border: %(stroke).3fcqw solid var(--ink); border-radius: .25cqw;
     padding: .55em .8em; text-align: left; font-family: '%(caption_font)s', 'Comic Sans MS', sans-serif;
     --mw: 62%%; }
.b.caption b { font-size: 1.22em; }  /* **Name** im Kasten hervorheben, z. B. Steckbrief */
.b.sfx { font-family: '%(sfx)s', Impact, 'Arial Black', sans-serif; font-weight: 400; color: var(--c, var(--accent));
     font-size: calc(%(sfxsize).2fcqw * var(--s, 1)); letter-spacing: .03em; line-height: 1; -webkit-text-stroke: %(sfxstroke).3fcqw var(--ink);
     paint-order: stroke fill; transform: translate(var(--tx, 0), var(--ty, 0)) rotate(var(--rot, -8deg));
     --mw: 90%%; text-transform: uppercase; }
.b.title { font-family: '%(sfx)s', Impact, 'Arial Black', sans-serif; font-weight: 400; color: var(--c, var(--accent));
     font-size: calc(%(titlesize).2fcqw * var(--s, 1)); letter-spacing: .03em; line-height: 1.02; width: var(--mw, 92%%);
     max-width: none; -webkit-text-stroke: %(titlestroke).3fcqw var(--ink); paint-order: stroke fill;
     text-shadow: .28cqw .32cqw 0 var(--ink); }
.pageno { position: absolute; bottom: %(pnb)dpx; width: 100%%; text-align: center; font: 1.1cqw Helvetica, Arial;
     color: #555; }
@page { size: %(pdfsize)s; margin: 0; }
@media print {
  html, body { background: none; }
  .page { width: %(pdfw)s; height: %(pdfh)s; break-after: page; }
}
"""

JS = r"""
function drawTails() {
  const NS = 'http://www.w3.org/2000/svg';
  for (const panel of document.querySelectorAll('.panel')) {
    const pr = panel.getBoundingClientRect();
    const under = panel.querySelector('svg.under'), over = panel.querySelector('svg.over');
    for (const b of panel.querySelectorAll('.b[data-tail]')) {
      const r = b.getBoundingClientRect();
      const sw = parseFloat(getComputedStyle(b).borderTopWidth) || 2;
      const cx = r.left - pr.left + r.width / 2, cy = r.top - pr.top + r.height / 2;
      const rx = r.width / 2, ry = r.height / 2;
      let tx, ty;
      if (b.dataset.tail === 'auto') { tx = cx + rx * 0.25; ty = cy + ry + pr.height * 0.12; }
      else {
        const [x, y] = b.dataset.tail.split(',').map(Number); tx = x * pr.width; ty = y * pr.height;
        // tail = Mund; der Zeiger endet kurz davor, damit er nicht ins Gesicht ragt
        const gap = 0.08 * Math.min(pr.width, pr.height), dl = Math.hypot(tx - cx, ty - cy);
        if (dl > gap * 2) { tx -= (tx - cx) / dl * gap; ty -= (ty - cy) / dl * gap; }
      }
      const dx = tx - cx, dy = ty - cy;
      const phi = Math.atan2(dy / ry, dx / rx);
      const px = cx + rx * Math.cos(phi) * 0.92, py = cy + ry * Math.sin(phi) * 0.92;
      const len = Math.hypot(tx - px, ty - py) || 1;
      if (len < 4) continue;
      const nx = -(ty - py) / len, ny = (tx - px) / len;
      if (b.classList.contains('thought')) {
        const m = Math.min(rx, ry);
        [[0.35, 0.18], [0.65, 0.12], [0.9, 0.07]].forEach(([t, s]) => {
          const c = document.createElementNS(NS, 'ellipse');
          c.setAttribute('cx', px + (tx - px) * t); c.setAttribute('cy', py + (ty - py) * t);
          c.setAttribute('rx', m * s * 1.25); c.setAttribute('ry', m * s);
          c.setAttribute('fill', 'var(--paper)'); c.setAttribute('stroke', 'var(--ink)');
          c.setAttribute('stroke-width', sw); over.appendChild(c);
        });
        continue;
      }
      const wb = Math.max(Math.min(rx, ry) * 0.42, sw * 6);
      const b1 = [px + nx * wb / 2, py + ny * wb / 2], b2 = [px - nx * wb / 2, py - ny * wb / 2];
      // leicht gebogener Zeiger: Kontrollpunkte etwas zur Seite versetzt
      const bend = 0.12 * len;
      const c1 = [(b1[0] + tx) / 2 + nx * bend * 0.2, (b1[1] + ty) / 2 + ny * bend * 0.2];
      const c2 = [(b2[0] + tx) / 2 + nx * bend * 0.2, (b2[1] + ty) / 2 + ny * bend * 0.2];
      const d = `M${b1} Q${c1} ${tx},${ty} Q${c2} ${b2} Z`;
      const p1 = document.createElementNS(NS, 'path');
      p1.setAttribute('d', d); p1.setAttribute('fill', 'var(--paper)'); p1.setAttribute('stroke', 'var(--ink)');
      p1.setAttribute('stroke-width', sw); p1.setAttribute('stroke-linejoin', 'round');
      if (b.classList.contains('whisper')) p1.setAttribute('stroke-dasharray', `${sw * 2.5} ${sw * 1.6}`);
      under.appendChild(p1);
      // Abdeckung über der Blase: verdeckt deren Rand am Zeigeransatz
      const i1 = [px + nx * (wb / 2 - sw), py + ny * (wb / 2 - sw)], i2 = [px - nx * (wb / 2 - sw), py - ny * (wb / 2 - sw)];
      const mid = [px + (tx - px) * 0.3, py + (ty - py) * 0.3];
      const back = [px - (tx - px) / len * sw * 2, py - (ty - py) / len * sw * 2];
      const p2 = document.createElementNS(NS, 'path');
      p2.setAttribute('d', `M${back} L${i1} L${mid} L${i2} Z`); p2.setAttribute('fill', 'var(--paper)');
      over.appendChild(p2);
    }
  }
  document.body.dataset.ready = '1';
}
// erst nach Schriften und Bildern zeichnen – sonst ändern sich die Blasengrößen danach
window.addEventListener('load', () => document.fonts.ready.then(drawTails));
"""


def _text(t: str) -> str:
    t = html.escape(t.strip())
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t.replace("\n", "<br>")


def bubble_html(b: dict, idx_by_kind: dict) -> str:
    kind = b.get("type", "speech")
    group = kind if kind in ("caption", "sfx") else "other"
    pos = b.get("pos")
    if pos is None:
        opts = DEFAULT_POS[group]
        pos = opts[min(idx_by_kind.get(group, 0), len(opts) - 1)]
        idx_by_kind[group] = idx_by_kind.get(group, 0) + 1
    style = []
    if isinstance(pos, dict):
        style.append(f"left:{pos.get('x', 0.05) * 100:.2f}%;top:{pos.get('y', 0.05) * 100:.2f}%")
        if pos.get("w"):
            style.append(f"--mw:{pos['w'] * 100:.1f}%")
    else:
        style.append(POS_CSS[pos])
    if kind == "sfx" and "rot" in b:
        style.append(f"--rot:{b['rot']}deg")
    if b.get("color"):  # nur title/sfx: Füllfarbe
        style.append(f"--c:{b['color']}")
    if b.get("size"):  # Faktor auf die Schriftgröße, z. B. 1.3
        style.append(f"--s:{float(b['size'])}")
    tail = ""
    if kind in ("speech", "thought", "whisper", "shout") and b.get("tail") != "none" and b.get("who") != "off":
        t = b.get("tail")
        tail = f' data-tail="{t["x"]},{t["y"]}"' if isinstance(t, dict) else ' data-tail="auto"'
    who = f' data-who="{html.escape(b["who"])}"' if b.get("who") else ""
    return f'<div class="b {kind}" style="{";".join(style)}"{tail}{who}>{_text(b["text"])}</div>'


def page_html(c: dict, pg: dict, geo: dict, pdir: Path, number: int | None) -> str:
    parts = []
    full = " fullbleed" if pg.get("fullBleed") else ""
    for pn, (x, y, w, h) in zip(pg["panels"], panel_rects(pg, geo)):
        img = (pn.get("assets") or {}).get("image")
        src = pdir / img if img else None
        if src and src.exists():
            f = pn.get("focus") or {}
            ist = (f'object-position:{f.get("x", 0.5) * 100:.1f}% {f.get("y", 0.5) * 100:.1f}%;'
                   f'object-fit:{pn.get("fit", "cover")}')
            if pn.get("pad"):  # Bildfläche innerhalb des Panels (Anteile), z. B. Platz für einen Steckbrief
                pd = {"t": 0, "r": 0, "b": 0, "l": 0, **pn["pad"]}
                ist += (f';position:absolute;left:{pd["l"] * 100:.2f}%;top:{pd["t"] * 100:.2f}%;'
                        f'width:{(1 - pd["l"] - pd["r"]) * 100:.2f}%;height:{(1 - pd["t"] - pd["b"]) * 100:.2f}%')
            art = f'<img src="{src.resolve().as_uri()}" style="{ist}">'
        elif pn.get("blank"):
            art = ""
        else:
            art = f'<div class="ph"><b>{pn["id"]} · {pn.get("shot", "")}</b>{html.escape(pn.get("prompt", ""))}</div>'
        astyle = []
        if pn.get("bg"):
            astyle.append(f"background:{pn['bg']}")
        if pn.get("frame") is False:
            astyle.append("border:0")
        astyle = f' style="{";".join(astyle)}"' if astyle else ""
        idx: dict = {}
        bubbles = "".join(bubble_html(b, idx) for b in pn.get("bubbles", []))
        style = (f"left:{x / geo['W'] * 100:.4f}%;top:{y / geo['H'] * 100:.4f}%;"
                 f"width:{w / geo['W'] * 100:.4f}%;height:{h / geo['H'] * 100:.4f}%")
        parts.append(f'<div class="panel{full}" id="{pn["id"]}" style="{style}"><div class="art"{astyle}>{art}</div>'
                     f'<svg class="tails under"></svg>{bubbles}<svg class="tails over"></svg></div>')
    if number is not None:
        parts.append(f'<div class="pageno">{number}</div>')
    return f'<div class="page" id="{pg["id"]}">{"".join(parts)}</div>'


def document(c: dict, pages_html: list[str], geo: dict) -> str:
    st = c["style"]
    pal = {"paper": "#FFFFFF", "ink": "#111111", "caption": "#FFF3B0", "accent": "#E4572E", **(st.get("palette") or {})}
    fonts = {"dialogue": "Comic Neue", "caption": "Comic Neue", "sfx": "Bangers", **(st.get("fonts") or {})}
    faces = []
    for (fam, weight), file in FONT_FILES.items():
        p = REPO / "fonts" / file
        if p.exists():
            faces.append(f"@font-face {{ font-family: '{fam}'; font-weight: {weight}; "
                         f"src: url('{p.resolve().as_uri()}'); }}")
    letter = float((st.get("lettering") or {}).get("size", geo["letter"]))
    if geo["mm"]:
        wmm, hmm = geo["mm"]
        pdfw, pdfh = f"{wmm:.2f}mm", f"{hmm:.2f}mm"
    else:  # Bildschirmformate: 1 px = 1/96 in
        pdfw, pdfh = f"{geo['W']}px", f"{geo['H']}px"
    css = CSS % {
        "fontfaces": "\n".join(faces), **pal, "W": geo["W"], "H": geo["H"],
        "dialogue": fonts["dialogue"], "caption_font": fonts["caption"], "sfx": fonts["sfx"],
        "letter": letter, "letter2": letter * 1.12, "sfxsize": letter * 3.2, "sfxstroke": letter * 0.09,
        "titlesize": letter * 4.2, "titlestroke": letter * 0.22,
        "stroke": 0.16 if geo["W"] > 2000 else 0.22, "stroke2": 0.32 if geo["W"] > 2000 else 0.4,
        "border": 0.22 if geo["W"] > 2000 else 0.3,
        "upper": "text-transform: uppercase;" if (st.get("lettering") or {}).get("uppercase") else "",
        "pnb": max(geo["bleed"] + geo["margin"] // 4, 8), "pdfsize": f"{pdfw} {pdfh}", "pdfw": pdfw, "pdfh": pdfh,
    }
    return (f'<!doctype html><html lang="{c.get("language", "de")}"><head><meta charset="utf-8">'
            f"<title>{html.escape(c['title'])}</title><style>{css}</style></head><body>"
            f"{''.join(pages_html)}<script>{JS}</script></body></html>")


def _chrome_cmd(pdir: Path, *args: str) -> list[str]:
    exe = chrome() or die("Kein Chrome/Chromium gefunden – installieren oder COMGEN_CHROME setzen")
    prof = pdir / ".work" / "chrome"
    prof.mkdir(parents=True, exist_ok=True)
    return [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--no-default-browser-check", "--allow-file-access-from-files", f"--user-data-dir={prof}",
            "--force-device-scale-factor=1", "--virtual-time-budget=15000", *args]


def cmd_render(a) -> None:
    pdir = project_dir(a.project)
    c = load_comic(pdir)
    errs, warns = validate(c, pdir)
    if errs:
        die("comic.json ungültig:\n" + "\n".join(errs))
    geo = page_geometry(c["format"])
    wanted = select([pg["id"] for pg in c["pages"]], a.page)
    numbers = c["format"].startswith("print") and c.get("pageNumbers", True)
    out = pdir / "pages"
    hdir = out / "html"
    hdir.mkdir(parents=True, exist_ok=True)
    pages = [(i, pg) for i, pg in enumerate(c["pages"], 1) if not wanted or pg["id"] in wanted]
    missing = [pn["id"] for _, pg in pages for pn in pg["panels"]
               if not pn.get("blank") and not ((pn.get("assets") or {}).get("image") and (pdir / pn["assets"]["image"]).exists())]
    if missing:
        print(f"⚠ ohne Bild (Platzhalter): {', '.join(missing)}")
    if not a.no_png:
        for i, pg in pages:
            f = hdir / f"{pg['id']}.html"
            f.write_text(document(c, [page_html(c, pg, geo, pdir, i if numbers else None)], geo), encoding="utf-8")
            png = out / f"{pg['id']}.png"
            cp = run(_chrome_cmd(pdir, f"--window-size={geo['W']},{geo['H']}", f"--screenshot={png}", f.as_uri()),
                     timeout=180)
            if cp.returncode or not png.exists():
                die(f"Chrome-Screenshot {pg['id']} fehlgeschlagen:\n{cp.stderr[-1500:]}")
            print(f"✔ pages/{png.name}  ({geo['W']}×{geo['H']})")
    if a.pdf or c["format"].startswith("print") or a.no_png:
        # immer das ganze Heft – mit --page entstünde sonst ein PDF, das nur diese Seiten enthält
        pages = list(enumerate(c["pages"], 1))
        f = hdir / "all.html"
        f.write_text(document(c, [page_html(c, pg, geo, pdir, i if numbers else None) for i, pg in pages], geo),
                     encoding="utf-8")
        pdf = out / f"{c['slug']}.pdf"
        cp = run(_chrome_cmd(pdir, f"--print-to-pdf={pdf}", "--no-pdf-header-footer", f.as_uri()), timeout=300)
        if cp.returncode or not pdf.exists():
            die(f"PDF fehlgeschlagen:\n{cp.stderr[-1500:]}")
        note = " – mit Beschnitt, RGB (Druckerei nach CMYK-Wunsch fragen)" if geo["mm"] else ""
        print(f"✔ pages/{pdf.name}  ({len(pages)} Seiten{note})")


def cmd_sheet(a) -> None:
    pdir = project_dir(a.project)
    c = load_comic(pdir)
    pngs = [pdir / "pages" / f"{pg['id']}.png" for pg in c["pages"]]
    pngs = [p for p in pngs if p.exists()]
    if not pngs:
        die("Noch keine Seiten – erst python3 tools/layout.py")
    n = len(pngs)
    cols = min(4, n)
    rows = -(-n // cols)
    inputs = [x for p in pngs for x in ("-i", str(p))]
    fc = ("".join(f"[{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,scale=-2:900,"
          f"pad=iw+30:ih+30:15:15:#777777,tile={cols}x{rows}:color=#777777")
    dst = pdir / "review" / "sheet.png"
    dst.parent.mkdir(exist_ok=True)
    cp = run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-frames:v", "1",
              "-update", "1", str(dst)])
    if cp.returncode:
        die(f"ffmpeg: {cp.stderr[-800:]}")
    print(f"✔ review/sheet.png ({len(pngs)} Seiten)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", dest="project", help="Comicordner (Default: comic/)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("sheet", help="Übersicht aller Seiten")
    ap.add_argument("--page", help="Seiten-IDs, kommagetrennt (nur PNGs; das PDF enthält immer alle Seiten)")
    ap.add_argument("--pdf", action="store_true", help="PDF auch für Web/Social")
    ap.add_argument("--no-png", action="store_true", help="nur PDF")
    a = ap.parse_args()
    cmd_sheet(a) if a.cmd == "sheet" else cmd_render(a)


if __name__ == "__main__":
    main()
