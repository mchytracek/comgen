---
name: comfyui
description: Steuert ComfyUI (lokal oder entfernter Rechner) für Comics – Panel-Bilder mit Z-Image Turbo, Figuren aus Fotos und Figurentausch mit Qwen Image 2.1 Edit, Jobs überwachen, Ergebnisse prüfen, Workflows anpassen, Fehler beheben. Verwenden in Phase 5 des Comic-Workflows, wenn Panels oder Figuren erzeugt werden, oder bei ComfyUI-Fehlern.
---

# ComfyUI für Comics

Werkzeuge: MCP-Server **`comfy-mcp`** und die Python-Tools – beide nutzen `comfy-cli`.
Workflows und Slot-Adressen: `comfy/workflows/README.md`. Für die Comic-Pipeline immer die
Tools nehmen; MCP für Diagnose (`server_info`, `job`, `get_logs`) und Experimente.

## Panels erzeugen

```bash
python3 tools/panels.py                        # alle fehlenden Panels
python3 tools/panels.py --page p02             # eine Seite
python3 tools/panels.py --only p02-3 --force   # neu (Bildaufbau + Figuren)
python3 tools/panels.py --only p02-3 --reswap  # nur Figuren neu einsetzen
python3 tools/panels.py --dry-run              # Prompts/Größen zeigen
```

Pro Panel: **Z-Image** baut das Bild im Seitenverhältnis des Panel-Rahmens auf (Einstellung +
`prompt` + `look` der Figuren + `style.imagePrompt`), dann setzt **Qwen Image 2.1 Edit** jede
Figur mit Comic-Referenz ein (ein Durchgang pro Figur, `where` sagt welche). Ergebnis
`comic/assets/panels/<id>.png`, Zwischenstufen `<id>_base.png`, `<id>_s0.png` …
Dauer (Apple Silicon, MPS): Z-Image ~20–30 s, je Figurentausch ~15–40 s.
Lange Läufe im Hintergrund starten. `panels.py` lädt `comic.json` vor jedem Schreiben neu.

**Erst ein Panel mit Figur erzeugen und zeigen** (Stil + Ähnlichkeit), dann den Rest.
Jedes Bild mit `Read` ansehen – bei Problemen:

| Problem | Maßnahme |
|---------|----------|
| Figur unähnlich | `--reswap`; `expression`/`wear` konkret; bessere Referenz (`cast.py render/pick`) |
| falsche Person ersetzt | `where` präzisieren („the woman sitting on the left“), im `prompt` Positionen nennen |
| Figur doppelt / Fremde im Bild | `prompt` vereinfachen, `wide` → `medium`, neuer `seed` |
| Text/Pseudotext im Bild | Bildschirme/Schilder ohne Inhalt beschreiben („showing a chart“) |
| Stil weicht ab | `style.imagePrompt` schärfen; nie pro Panel abweichende Stilwörter |
| Komposition passt nicht zum Rahmen | `shot` ändern; `panel.focus` verschiebt den Ausschnitt |

## Prompting

- **Z-Image Turbo** (englisch): Einstellung → Ort → Handlung → Requisiten → Licht. Keine
  Negativ-Prompts. Kein Text im Bild anfordern.
- **Qwen Image Edit**: Imperativ, Bilder als `<image1>` (Panel) / `<image2>` (Figur); was bleiben
  soll pauschal („keep everything else unchanged“), was sich ändern soll konkret (Mimik, Kleidung).
  Die Prompts baut `panels.py` (`swap_prompt`) bzw. `cast.py`.

## Entfernter ComfyUI-Server

Adresse `$COMFYUI_URL` > `.comgen.env` > `~/.config/comgen/env` > `~/.config/vidgen/env` > lokal
(`python3 tools/_common.py comfy-url`). Ergebnisse kommen per HTTP nach `comic/.work/comfy_out/`,
Eingaben (Fotos, Referenzen, Zwischenbilder) per Upload. object_info lädt `_common.py` selbst
(comfy-cli ≥ 1.13 holt es sonst nur von Loopback). `server_info`-Hardware beschreibt diesen Mac,
nicht den Server. Modelle auf dem Server installieren.

## Fehlerbehebung

| Symptom | Maßnahme |
|---------|----------|
| nicht erreichbar | User bitten, ComfyUI zu starten; `scripts/doctor.sh` |
| `unknown_class_type` | Custom Node fehlt → `workflow_deps`, `install_node` (User fragen) |
| `unknown_enum_value` bei Modell | `search_models`, ggf. `download_model` (User fragen, groß) |
| MPS Out-of-Memory | `free_memory`, kleinere Panels, nacheinander |
| Job hängt | `job(action="status")`, `get_logs(tail=200)` |

**Nie ohne Zustimmung:** `partner_generate`, `confirm_spend=true`, `install_node`,
`download_model`, `update_comfyui`, `restart_comfyui`.
