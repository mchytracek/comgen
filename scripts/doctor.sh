#!/usr/bin/env bash
# Prüft alle Komponenten der Comic-Produktion. Ändert nichts.
set -u
cd "$(dirname "$0")/.."
COMFY_URL=$(python3 tools/_common.py comfy-url 2>/dev/null || echo "http://127.0.0.1:8188")
export COMFY_LOCAL_URL="$COMFY_URL"
case "$COMFY_URL" in http://127.*|http://localhost*|http://\[::1\]*) REMOTE=0 ;; *) REMOTE=1 ;; esac
ok()   { printf "  \033[32m✔\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$*"; }
bad()  { printf "  \033[31m✖\033[0m %s\n" "$*"; }

echo "System"
for b in python3 git; do
  command -v "$b" >/dev/null && ok "$b $($b --version 2>&1 | head -1)" || bad "$b fehlt"
done
command -v ffmpeg >/dev/null && ok "ffmpeg" || bad "ffmpeg fehlt → brew install ffmpeg (Fotos, Vergleichsbilder, Übersicht)"
command -v ffprobe >/dev/null && ok "ffprobe" || bad "ffprobe fehlt → brew install ffmpeg"
CH=$(python3 tools/_common.py chrome)
[ -n "$CH" ] && ok "Browser für das Seitenlayout: $CH" || bad "kein Chrome/Chromium/Edge → installieren oder COMGEN_CHROME=/pfad setzen"
for f in ComicNeue-Regular.ttf ComicNeue-Bold.ttf Bangers-Regular.ttf; do
  [ -f "fonts/$f" ] || warn "Schrift fonts/$f fehlt → scripts/setup.sh --fonts (Fallback: Comic Sans MS)"
done
[ -f fonts/ComicNeue-Bold.ttf ] && ok "Lettering-Schriften (Comic Neue, Bangers)"

echo "ComfyUI"
[ "$REMOTE" = 1 ] && ok "entfernter Server: $COMFY_URL (aus .comgen.env / ~/.config/comgen/env / \$COMFYUI_URL)"
if stats=$(curl -s -m 3 "$COMFY_URL/system_stats"); then
  ver=$(printf '%s' "$stats" | python3 -c 'import json,sys;print(json.load(sys.stdin)["system"]["comfyui_version"])' 2>/dev/null)
  [ -n "$ver" ] && ok "läuft auf $COMFY_URL (v$ver)" || bad "$COMFY_URL antwortet, aber nicht wie ComfyUI"
else
  if [ "$REMOTE" = 1 ]; then bad "nicht erreichbar auf $COMFY_URL – ComfyUI dort mit --listen 0.0.0.0 starten, Firewall/VPN prüfen"
  else bad "nicht erreichbar auf $COMFY_URL – ComfyUI starten"; fi
fi
command -v comfy >/dev/null && ok "comfy-cli" || bad "comfy-cli fehlt → uv tool install comfy-cli"
command -v comfy-mcp >/dev/null && ok "comfy-mcp installiert" || bad "comfy-mcp fehlt → scripts/setup.sh --mcp"

echo "Workflows (gegen laufendes ComfyUI)"
OI=$(mktemp -t comgen-object_info.XXXXXX)
trap 'rm -f "$OI"' EXIT
if curl -s -m 60 -f "$COMFY_URL/object_info" -o "$OI"; then
  for f in comfy/workflows/*.json; do
    r=$(comfy --json validate --workflow "$f" --input "$OI" 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin); x=d.get("data") or {}
errs=x.get("errors") or ([d["error"]] if d.get("error") else [])
# Eingabebilder setzen die Tools erst zur Laufzeit per Upload
errs=[e for e in errs if not (e.get("code")=="unknown_enum_value"
      and any(ext in e.get("message","") for ext in (".png",".jpg",".jpeg",".webp")))]
if (d.get("ok") or d.get("data")) and not errs: print("ok")
else: e=errs[0] if errs else {}; print(e.get("code","?")+": "+str(e.get("message",""))[:90])' 2>/dev/null)
    name=$(basename "$f" .json)
    [ "$r" = "ok" ] && ok "$name" || warn "$name – ${r:-nicht prüfbar}"
  done
else
  warn "object_info von $COMFY_URL nicht ladbar – Workflows nicht geprüft"
fi

echo "Skills"
for s in comic cast story panels comfyui lettering comic-review comgen-setup; do
  [ -f ".claude/skills/$s/SKILL.md" ] || bad "eigener Skill fehlt: $s"
done
ok "eigene Skills vorhanden"

echo "Comic"
if [ -f comic/comic.json ]; then
  python3 tools/comic.py show | head -1 | sed 's/^# /  /'
  python3 tools/comic.py validate 2>&1 | sed 's/^/  /' | tail -5
else
  warn "noch nicht initialisiert → scripts/init.sh \"<Titel>\""
fi
git remote get-url template >/dev/null 2>&1 && ok "Template-Remote: $(git remote get-url template)" \
  || warn "kein Remote 'template' (Updates: git remote add template <url>)"
