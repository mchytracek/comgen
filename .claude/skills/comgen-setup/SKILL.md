---
name: comgen-setup
description: Richtet die Comic-Produktion ein und diagnostiziert sie – ComfyUI-Verbindung (lokal oder entfernt), comfy-cli/comfy-mcp, Modelle (Z-Image Turbo, Qwen Image 2.1 Edit), Headless-Chrome fürs Layout, Lettering-Schriften, FFmpeg. Verwenden bei Ersteinrichtung oder wenn Werkzeuge fehlen bzw. ComfyUI/MCP nicht reagiert.
---

# Setup & Diagnose

1. `scripts/doctor.sh` ausführen und lesen – ✔/⚠/✖ je Komponente.
2. Fehlendes mit dem User klären, dann `scripts/setup.sh` (oder `--mcp`, `--fonts`).

| Komponente | Prüfen | Einrichten |
|------------|--------|-----------|
| ComfyUI-Adresse | `python3 tools/_common.py comfy-url` | `scripts/init.sh --comfy-url …` bzw. `.comgen.env` |
| ComfyUI läuft | `curl -s "$(python3 tools/_common.py comfy-url)/system_stats"` | lokal starten; remote dort `python main.py --listen 0.0.0.0` |
| comfy-cli, comfy-mcp | `command -v comfy comfy-mcp` | `scripts/setup.sh --mcp`, Claude Code neu starten |
| Z-Image Turbo, Qwen Image 2.1 Turbo Edit | doctor.sh → Workflows | Modelle laut `comfy/workflows/README.md` (MCP `download_model`, nur nach Zustimmung, mehrere GB) |
| Chrome/Chromium | `python3 tools/_common.py chrome` | installieren oder `COMGEN_CHROME=/pfad` |
| Schriften | `ls fonts/` | `scripts/setup.sh --fonts` |
| FFmpeg | `command -v ffmpeg` | `brew install ffmpeg` |

Entfernter ComfyUI-Server: Adresse `$COMFYUI_URL` > `.comgen.env` > `~/.config/comgen/env` >
`~/.config/vidgen/env` > lokal. Modelle/Custom Nodes müssen auf dem Server liegen –
`download_model`/`install_node` aus dieser Sitzung wirken lokal. Nur `http://host:port`;
nicht offen ins Internet stellen (VPN/SSH-Tunnel). Nach Änderungen an `.mcp.json` oder
`.comgen.env` Claude Code neu starten.

**Nie ohne Zustimmung:** `partner_generate`, `confirm_spend=true`, `install_node`,
`download_model`, `update_comfyui`, `restart_comfyui`.
