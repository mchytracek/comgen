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
python3 tools/panels.py edit p02-3 "Remove the second boy on the right."      # nachbearbeiten
python3 tools/panels.py edit p02-3 "Replace the two unknown children with the characters from <image2> …" --ref robin,nilo
```

Pro Panel: **Z-Image** baut das Bild im Seitenverhältnis des Panel-Rahmens auf (Einstellung +
`prompt` + `look` der Figuren + `style.imagePrompt`), dann setzt **Qwen Image 2.1 Edit** die
Figuren mit Comic-Referenz ein – gruppenweise mit einem **Vorlagenblatt** (Referenzen nebeneinander):

1. alle Tiere (`cast[].animal: true`) in einem Durchgang,
2. alle übrigen Figuren in einem Durchgang,
3. jede Hauptfigur (`cast[].hero: true`) allein, zuletzt – sie wird danach nicht mehr überschrieben.

Jeder Durchgang bekommt einen eigenen Seed. Das ist deutlich sauberer als ein Durchgang pro
Figur (`--swap single`, die alte Variante): weniger Bildrauschen, weniger doppelte Figuren.
`where` sagt, welche Figur im Bild gemeint ist; `cast[].kind` sagt, was sie ist („girl“,
„grandfather“, „ginger spitz dog“) – ohne `kind` heißt jede Figur „person“, und Tiere werden
dann schlecht getroffen. Ergebnis `comic/assets/panels/<id>.png`, Zwischenstufen `<id>_base.png`,
`<id>_g0.png` … Dauer (Apple Silicon, MPS): Z-Image ~20–30 s, je Durchgang ~80–250 s.

`edit` bearbeitet ein fertiges Panel (Figur entfernen, Requisite ergänzen, Größe korrigieren);
mit `--ref` ersetzt es fremde Personen durch Figuren aus dem Cast. Das Original bleibt als
`<id>_pre_edit.png`, weitere `edit`-Aufrufe bauen auf dem aktuellen Bild auf.
Lange Läufe im Hintergrund starten. `panels.py` lädt `comic.json` vor jedem Schreiben neu.

**Erst ein Panel mit Figur erzeugen und zeigen** (Stil + Ähnlichkeit), dann den Rest.
Jedes Bild mit `Read` ansehen – bei Problemen:

| Problem | Maßnahme |
|---------|----------|
| Figur unähnlich | `--reswap`; `expression`/`wear` konkret; bessere Referenz (`cast.py render/pick`) |
| falsche Person ersetzt | `where` präzisieren („the woman sitting on the left“), im `prompt` Positionen nennen |
| Figur doppelt / Fremde im Bild | `edit` („Remove the second girl on the right“) oder `edit --ref <id>`; sonst `prompt` vereinfachen, neuer `seed` |
| Größenverhältnisse falsch (Kleinkind größer als großes Kind) | im `prompt` ausdrücklich nennen („the 5-year-old girl is clearly the tallest child“); `edit` („Make the boy smaller …“) |
| Tier wird zum Menschen / bekommt falsche Merkmale | `kind` + `animal` setzen; Z-Image ignoriert Verneinungen („no mane“) – positiv beschreiben („like a puma“) |
| Platz für Text fehlt | im `prompt` freie Fläche reservieren („empty sky in the upper third“) |
| Text/Pseudotext im Bild | Bildschirme/Schilder ohne Inhalt beschreiben („showing a chart“) |
| Stil weicht ab | `style.imagePrompt` schärfen; nie pro Panel abweichende Stilwörter |
| Komposition passt nicht zum Rahmen | `shot` ändern; `panel.focus` verschiebt den Ausschnitt |

## Prompting

- **Z-Image Turbo** (englisch): Einstellung → Ort → Handlung → Requisiten → Licht. Keine
  Negativ-Prompts. Kein Text im Bild anfordern.
- **Qwen Image Edit**: Imperativ, Bilder als `<image1>` (Panel) / `<image2>` (Figur); was bleiben
  soll pauschal („keep everything else unchanged“), was sich ändern soll konkret (Mimik, Kleidung).
  Die Prompts baut `panels.py` (`group_prompt`, `swap_prompt`) bzw. `cast.py`.

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
