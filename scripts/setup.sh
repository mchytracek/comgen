#!/usr/bin/env bash
# Einrichtung der Comic-Produktion – einmal pro Rechner (nicht pro Comic).
#   scripts/setup.sh            # alles (MCP, Schriften, Prüfung)
#   scripts/setup.sh --mcp      # nur comfy-cli + comfy-mcp
#   scripts/setup.sh --fonts    # nur Lettering-Schriften (Comic Neue, Bangers – OFL) nach fonts/
# Modelle und Custom Nodes werden NICHT automatisch installiert (comfy/workflows/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."
want="${1:-all}"

step() { printf "\n\033[1m▶ %s\033[0m\n" "$*"; }

if [[ "$want" == all || "$want" == --mcp ]]; then
  step "comfy-cli und comfy-mcp"
  command -v uv >/dev/null || { echo "uv fehlt: https://docs.astral.sh/uv/"; exit 1; }
  command -v comfy >/dev/null || uv tool install "comfy-cli>=1.14.0"
  command -v comfy-mcp >/dev/null || uv tool install comfy-mcp
  echo "  ComfyUI auf anderem Rechner? Lokale Installation nicht nötig – scripts/init.sh --comfy-url http://host:8188"
fi

if [[ "$want" == all || "$want" == --fonts ]]; then
  step "Lettering-Schriften (SIL Open Font License) → fonts/"
  base=https://raw.githubusercontent.com/google/fonts/main/ofl
  for f in comicneue/ComicNeue-Regular.ttf comicneue/ComicNeue-Bold.ttf bangers/Bangers-Regular.ttf; do
    [[ -f "fonts/$(basename "$f")" ]] || curl -sfL -o "fonts/$(basename "$f")" "$base/$f" && echo "  ✔ $(basename "$f")"
  done
fi

if [[ "$want" == all ]]; then
  command -v ffmpeg >/dev/null || echo "Hinweis: ffmpeg fehlt → brew install ffmpeg"
  [[ -n "$(python3 tools/_common.py chrome)" ]] || echo "Hinweis: Chrome/Chromium fehlt (Seitenlayout) → installieren"
  step "Prüfung"
  scripts/doctor.sh || true
fi
