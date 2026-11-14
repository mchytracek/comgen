# ComfyUI-Workflows

Offizielle ComfyUI-Vorlagen im UI-Format, übernommen aus vidgen. `comfy-cli` (und damit
`comfy-mcp`) setzt Werte über **Slot-Adressen** (`<node-id>.<feld>`). Aktuelle Slots:
MCP `list_workflow_slots` bzw. `comfy --json workflow slots <datei>`. Die Zuordnung in den
Tools steht in `tools/_common.py` (`IMAGE`, `QEDIT`, `QEDIT_REF`).

Einsatz in comgen:

| Workflow | Wofür | Tool |
|----------|-------|------|
| `image_z_image_turbo.json` | Bildaufbau jedes Panels; Figuren ohne Foto | `panels.py`, `cast.py add … --look` |
| `image_qwen_2_1_turbo_edit.json` | Foto einer Person → Comicfigur | `cast.py add/render` |
| `image_qwen_2_1_turbo_edit_ref.json` | Comicfigur ins Panel einsetzen (Bild 1 = Panel, Bild 2 = Figur) | `panels.py` |

## `image_z_image_turbo.json` – Text → Bild ✅ lauffähig

| Slot | Bedeutung | Default |
|------|-----------|---------|
| `57.text` | Prompt | – |
| `57.width` / `57.height` | Auflösung | 1024 / 1024 → für 16:9 **1344×768**, 9:16 **768×1344** |
| `57.seed` | Seed | 0 |
| `57.steps` | Schritte | 8 (Turbo: 8 reicht) |
| `9.filename_prefix` | Ausgabename | `z-image-turbo` |

## `image_qwen_2_1_turbo_edit.json` / `image_qwen_2_1_turbo_edit_ref.json` – Bild bearbeiten ✅ lauffähig

Qwen Image 2.1 Turbo Edit (Gallery-Vorlage `image_qwen_2_1_turbo_image_edit`, geprüft 2026-11-13 auf
ComfyUI v0.43). Einsatz: **wiederkehrende Figur** – Foto einer Person → Figur im Comicstil
(`_edit`, 1 Bild, `tools/cast.py`) und Figur in jedes Panelbild einsetzen
(`_edit_ref`, Bild 1 = Panelbild aus Z-Image, Bild 2 = Referenzfigur, `tools/panels.py`).
Im Prompt heißen die Bilder `<image1>`, `<image2>`.

Modelle: `qwen_image_2.1_turbo_int8_convrot.safetensors` (diffusion_models),
`qwen3vl_8b_int8_convrot.safetensors` (text_encoders), `qwen_image_2.1_vae_bf16.safetensors` (vae).

Gegenüber der Gallery-Vorlage gepatcht:
- Prompt-Link geht direkt vom Subgraph-Eingang an `TextEncodeQwenImage21` (Link 743). Die Vorlage
  führt ihn über einen `PreviewAny`-Node, der den Text erst in neueren ComfyUI-Versionen
  durchreicht – sonst kommt der Prompt **leer** an und das Modell gibt nur das Eingangsbild
  (bzw. freigestellt mit lila Hintergrund) zurück.
- Prompt-Enhancer (Qwen 3.5 9B) bleibt aus (`459.switch_1=false`); sein Lader zeigt auf das ohnehin
  nötige `qwen3vl_8b`, damit kein Zusatzmodell gebraucht wird.
- `_edit_ref`: zweiter `LoadImage` (Node 600) auf `images.image_2`. ImageCompare/Notizen entfernt.

| Slot | Bedeutung | Default |
|------|-----------|---------|
| `459.prompt` | Anweisung (englisch, `<image1>`/`<image2>`) | – |
| `459.width` / `459.height` | Ausgabegröße (bei `459.switch=false`) | 1024 / 1024 → 16:9 **1344×768** |
| `459.seed` | Seed | – |
| `470.image` | Bild 1 (Dateiname in `input/`) | `example.png` |
| `600.image` | Bild 2 / Referenz (nur `_edit_ref`) | `example.png` |
| `461.filename_prefix` | Ausgabename | `Qwen_image_2.1` |

Tipps: kleine Handyfotos vorher auf ≥ 1024 px hochskalieren. Beim Figurentausch Mimik/Handlung
und abweichende Kleidung ausdrücklich nennen – sonst übernimmt Qwen den neutralen Ausdruck und
die Kleidung der Referenz (z. B. Imkeranzug wird zum Hemd).

## Neue Workflows hinzufügen

1. `search_templates` / `fetch_template` (MCP) oder eigenen Workflow aus der ComfyUI-Oberfläche exportieren.
2. Hier ablegen, `validate_workflow` laufen lassen, Slot-Tabelle oben ergänzen.
3. In `tools/panels.py` (`WORKFLOWS`) die Slot-Zuordnung eintragen.
