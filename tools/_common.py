"""Gemeinsame Helfer für die comgen-Tools (nur Standardbibliothek)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COMIC = REPO / "comic"
WORKFLOWS = REPO / "comfy" / "workflows"
TEMPLATES = REPO / "templates"

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
CONFIG_HOME = Path(os.environ.get("COMGEN_CONFIG", "~/.config/comgen")).expanduser()

# ---------------------------------------------------------------------------
# Seitenformate. Maße in mm (Druck) bzw. px (Bildschirm); alles wird in Pixel
# der Ausgabe umgerechnet. `letter` = Schriftgröße der Sprechblasen in % der Seitenbreite.
# ---------------------------------------------------------------------------
MM = 25.4
FORMATS: dict[str, dict] = {
    "print-a4": {"label": "Druck A4 (210×297 mm, 3 mm Beschnitt, 300 dpi)", "unit": "mm",
                 "width": 210, "height": 297, "bleed": 3, "margin": 12, "gutter": 4, "dpi": 300,
                 "letter": 1.75},
    "print-us": {"label": "Druck US-Comic (6.625×10.25 in, 1/8 in Beschnitt, 300 dpi)", "unit": "mm",
                 "width": 168.3, "height": 260.4, "bleed": 3.2, "margin": 11, "gutter": 3.5, "dpi": 300,
                 "letter": 1.9},
    "print-a5-quer": {"label": "Druck A5 quer, Bilderbuch (210×148 mm, 3 mm Beschnitt, 300 dpi)", "unit": "mm",
                      "width": 210, "height": 148, "bleed": 3, "margin": 9, "gutter": 3, "dpi": 300,
                      "letter": 2.0, "genMP": 2.0},
    "web": {"label": "Web (1600×2400 px)", "unit": "px",
            "width": 1600, "height": 2400, "bleed": 0, "margin": 56, "gutter": 20, "letter": 1.9},
    "social-4x5": {"label": "Social Feed 4:5 (1080×1350 px, Karussell)", "unit": "px",
                   "width": 1080, "height": 1350, "bleed": 0, "margin": 40, "gutter": 16, "letter": 3.0},
    "social-1x1": {"label": "Social quadratisch (1080×1080 px)", "unit": "px",
                   "width": 1080, "height": 1080, "bleed": 0, "margin": 36, "gutter": 14, "letter": 3.0},
    "social-9x16": {"label": "Story/Reel hochkant (1080×1920 px)", "unit": "px",
                    "width": 1080, "height": 1920, "bleed": 0, "margin": 60, "gutter": 18, "letter": 3.2},
}


def page_geometry(fmt_key: str) -> dict:
    """Seite in Ausgabepixeln: Gesamtgröße inkl. Beschnitt, Satzspiegel, Steg."""
    f = FORMATS.get(fmt_key)
    if not f:
        die(f"Unbekanntes Format {fmt_key!r} – erlaubt: {', '.join(FORMATS)}")
    k = f["dpi"] / MM if f["unit"] == "mm" else 1.0
    px = lambda v: round(v * k)  # noqa: E731
    bleed = px(f["bleed"])
    w, h = px(f["width"]) + 2 * bleed, px(f["height"]) + 2 * bleed
    return {"key": fmt_key, "W": w, "H": h, "bleed": bleed, "margin": px(f["margin"]) + bleed,
            "gutter": px(f["gutter"]), "letter": f["letter"], "unit": f["unit"],
            "mm": (f["width"] + 2 * f["bleed"], f["height"] + 2 * f["bleed"]) if f["unit"] == "mm" else None}


# ---------------------------------------------------------------------------
# ComfyUI-Adresse (lokal oder entfernter Rechner)
# ---------------------------------------------------------------------------
def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip("'\"")
    return out


def comfy_url() -> str:
    """$COMFYUI_URL > .comgen.env (dieser Klon) > ~/.config/comgen/env > ~/.config/vidgen/env > lokal."""
    for val in (os.environ.get("COMFYUI_URL"),
                _read_env_file(REPO / ".comgen.env").get("COMFYUI_URL"),
                _read_env_file(CONFIG_HOME / "env").get("COMFYUI_URL"),
                _read_env_file(Path("~/.config/vidgen/env").expanduser()).get("COMFYUI_URL")):
        if val and val.strip():
            url = val.strip().rstrip("/")
            return url if "://" in url else f"http://{url}"
    return DEFAULT_COMFY_URL


def comfy_is_remote(url: str | None = None) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url or comfy_url()).hostname or ""
    return not (host in ("localhost", "::1") or host.startswith("127."))


def comfy_env() -> dict[str, str]:
    url = comfy_url()
    return {**os.environ, "COMFY_LOCAL_URL": url, "COMFYUI_URL": url}


# ---------------------------------------------------------------------------
# Projekt / comic.json
# ---------------------------------------------------------------------------
def die(msg: str, code: int = 1) -> None:
    print(f"✖ {msg}", file=sys.stderr)
    sys.exit(code)


def project_dir(arg: str | None = None) -> Path:
    p = Path(arg).expanduser() if arg else COMIC
    if not p.is_absolute():
        p = Path.cwd() / p
    if not (p / "comic.json").exists():
        die(f"Kein comic.json in {p} – erst `scripts/init.sh \"<Titel>\"` ausführen")
    return p.resolve()


def load_comic(pdir: Path) -> dict:
    return json.loads((pdir / "comic.json").read_text(encoding="utf-8"))


def save_comic(pdir: Path, c: dict) -> None:
    (pdir / "comic.json").write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_comic(pdir: Path, fn) -> dict:
    """comic.json frisch laden, `fn(c)` anwenden, speichern – lange Läufe überschreiben so keine
    Änderungen, die währenddessen am Skript gemacht wurden."""
    c = load_comic(pdir)
    fn(c)
    save_comic(pdir, c)
    return c


def patch_panel(pdir: Path, pid: str, fn) -> dict:
    def apply(c: dict) -> None:
        for pg in c.get("pages", []):
            for pn in pg.get("panels", []):
                if pn["id"] == pid:
                    fn(pn)
    return patch_comic(pdir, apply)


def all_panels(c: dict) -> list[tuple[dict, dict]]:
    return [(pg, pn) for pg in c.get("pages", []) for pn in pg.get("panels", [])]


def cast_by_id(c: dict) -> dict[str, dict]:
    return {m["id"]: m for m in c.get("cast", [])}


def select(items: list[str], only: str | None) -> set[str] | None:
    if not only:
        return None
    wanted = {s.strip() for s in only.split(",") if s.strip()}
    unknown = wanted - set(items)
    if unknown:
        die(f"Unbekannt: {', '.join(sorted(unknown))}")
    return wanted


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


# ---------------------------------------------------------------------------
# comfy-cli
# ---------------------------------------------------------------------------
_OBJECT_INFO: Path | None = None


def comfy_object_info() -> Path:
    """object_info des konfigurierten Servers als Datei – comfy-cli ≥ 1.13 holt es im lokalen
    Modus nur von Loopback-Adressen; für einen entfernten Server laden wir es selbst."""
    global _OBJECT_INFO
    if _OBJECT_INFO and _OBJECT_INFO.is_file():
        return _OBJECT_INFO
    import tempfile
    import urllib.request
    from urllib.parse import urlparse
    url = comfy_url()
    host = re.sub(r"[^A-Za-z0-9.-]", "_", urlparse(url).netloc)
    dst = Path(tempfile.gettempdir()) / f"comgen-object_info-{host}-{os.getpid()}.json"
    try:
        with urllib.request.urlopen(f"{url}/object_info", timeout=60) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError as exc:
        die(f"object_info von {url} nicht ladbar – läuft ComfyUI dort?\n{exc}")
    _OBJECT_INFO = dst
    return dst


def comfy(*args: str, timeout: int | None = None) -> dict:
    """`comfy --json …` aufrufen und das letzte envelope-Objekt zurückgeben."""
    if not shutil.which("comfy"):
        die("comfy-cli nicht gefunden (uv tool install comfy-cli)")
    if args[:1] == ("workflow",) and args[1:2] in (("set-slot",), ("slots",)) and comfy_is_remote() \
            and "--input" not in args:
        args = (*args[:2], "--input", str(comfy_object_info()), *args[2:])
    cp = run(["comfy", "--json", *args], timeout=timeout, env=comfy_env())
    env = None
    for line in cp.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "envelope":
                env = obj
    if env is None:
        die(f"comfy {' '.join(args[:2])}: keine JSON-Antwort\n{cp.stderr[-2000:]}")
    return env


def comfy_output(out: str, pdir: Path) -> Path:
    """Ausgabe eines comfy-run als lokale Datei (Pfad lokal, /view-URL bei entferntem Server)."""
    if not out.startswith(("http://", "https://")):
        return Path(out)
    import urllib.request
    from urllib.parse import parse_qs, urlparse
    name = Path(parse_qs(urlparse(out).query).get("filename", ["output.bin"])[0]).name
    dst = pdir / ".work" / "comfy_out" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(out, timeout=300) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError as exc:
        die(f"Download der ComfyUI-Ausgabe fehlgeschlagen: {out}\n{exc}")
    return dst


def run_workflow(pdir: Path, name: str, spec: dict, overrides: dict, timeout: int = 900,
                 dry: bool = False) -> Path | None:
    """Workflow-Vorlage kopieren, Slots setzen, ausführen, Ausgabe als lokale Datei liefern."""
    import time
    work = pdir / ".work" / f"{name}.json"
    work.parent.mkdir(exist_ok=True)
    shutil.copyfile(WORKFLOWS / spec["file"], work)
    pairs = [f"{spec[k]}={v}" for k, v in overrides.items()]
    if dry:
        print(f"  [dry] {spec['file']}: " + "  ".join(p[:90] for p in pairs))
        return None
    env = comfy("workflow", "set-slot", str(work), *pairs)
    if not env["ok"]:
        die(f"set-slot {name}: {env['error']}")
    t0 = time.time()
    env = comfy("run", "--workflow", str(work), "--wait", "--timeout", str(timeout), timeout=timeout + 60)
    if not env["ok"] or (env.get("data") or {}).get("status") != "completed":
        die(f"{name} fehlgeschlagen: {env.get('error') or env.get('data')}\n"
            "→ MCP get_logs / job(action='status') prüfen")
    outs = env["data"].get("outputs") or []
    if not outs:
        die(f"{name}: keine Ausgabedatei gemeldet")
    print(f"  ✔ {name} in {time.time() - t0:.0f} s")
    return comfy_output(outs[0], pdir)


def stage(pdir: Path, src: Path, name: str, dry: bool = False) -> str:
    """Datei unter `name` in ComfyUIs input/ hochladen (lokal oder entfernt)."""
    if not dry:
        staged = pdir / ".work" / name
        staged.parent.mkdir(exist_ok=True)
        shutil.copyfile(src, staged)
        env = comfy("upload", str(staged), "--overwrite")
        if not env["ok"]:
            die(f"Upload {name}: {env['error']}")
    return name


# Slot-Adressen (siehe comfy/workflows/README.md)
IMAGE = {"file": "image_z_image_turbo.json", "prompt": "57.text", "width": "57.width",
         "height": "57.height", "seed": "57.seed", "prefix": "9.filename_prefix"}
QEDIT = {"file": "image_qwen_2_1_turbo_edit.json", "prompt": "459.prompt", "width": "459.width",
         "height": "459.height", "seed": "459.seed", "image": "470.image", "prefix": "461.filename_prefix"}
QEDIT_REF = {**QEDIT, "file": "image_qwen_2_1_turbo_edit_ref.json", "ref": "600.image"}


def gen_size(aspect: float, megapixels: float = 1.2) -> tuple[int, int]:
    """Erzeugungsgröße für ein Seitenverhältnis (B/H): ~1,2 MP, Kanten Vielfache von 64."""
    import math
    h = math.sqrt(megapixels * 1_000_000 / aspect)
    w = h * aspect
    r = lambda v: max(512, min(2048, int(round(v / 64)) * 64))  # noqa: E731
    return r(w), r(h)


def image_size(path: Path) -> tuple[int, int] | None:
    cp = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
              "-of", "csv=p=0", str(path)])
    try:
        w, h = cp.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except ValueError:
        return None


def chrome() -> str | None:
    """Headless-fähigen Browser finden (Chrome, Chromium, Edge, Brave) – für das Seitenlayout."""
    env = os.environ.get("COMGEN_CHROME")
    cands = [env] if env else []
    cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
    cands += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    return next((c for c in cands if c and Path(c).exists()), None)


if __name__ == "__main__":
    if sys.argv[1:] == ["comfy-url"]:
        print(comfy_url())
    elif sys.argv[1:] == ["chrome"]:
        print(chrome() or "")
    else:
        die("Aufruf: python3 tools/_common.py comfy-url|chrome")
