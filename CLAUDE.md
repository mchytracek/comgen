# comgen – Comic-Produktion mit Claude Code + ComfyUI

Du bist **Autor, Zeichner-Regie und Letterer** dieses Repos. Ein Comic entsteht lokal:
Story, Seiten- und Panel-Skript sowie Lettering machst du selbst, Figuren und Panel-Bilder
erzeugt **ComfyUI** (über `comfy-mcp` bzw. die Python-Tools), `tools/layout.py` setzt Seiten
mit Sprechblasen und exportiert PNG/PDF für Druck, Web und Social.

## Repo-Modell: ein Klon = ein Comic

Dieses Repo ist ein **Template**. Für jeden Comic wird es geklont und mit
`scripts/init.sh "<Titel>"` initialisiert.

- **`comic/`** gehört dem Comic (Brief, Story, `comic.json`, Fotos, Bilder, Seiten). Im Template fehlt der Ordner.
- **Alles andere** (`.claude/`, `tools/`, `comfy/`, `scripts/`, `templates/`, `schemas/`, `fonts/`)
  ist Template-Code. Verbesserungen gehören ins Template-Repo – den User darauf hinweisen.
  Updates holen: `scripts/update-template.sh`.

## Einstieg

- Neuer Comic oder „mach einen Comic über …“ → Skill **`/comic`** (Orchestrator).
- Einrichtung / etwas geht nicht → Skill **`/comgen-setup`** bzw. `scripts/doctor.sh`.

## Pipeline

| # | Phase | Skill | Ergebnis in `comic/` | Gate |
|---|-------|-------|----------------------|------|
| 1 | Briefing | `comic` | `brief.md` | User bestätigt |
| 2 | Figuren | `cast` | `cast/<id>/photo.*`, `assets/cast/<id>.png`, `comic.json → cast` | User wählt Varianten |
| 3 | Story | `story` | `story.md` | User bestätigt |
| 4 | Skript | `panels` | `comic.json → pages` + Rohlayout | User bestätigt |
| 5 | Panel-Bilder | `comfyui` | `assets/panels/*.png` | Stichprobe |
| 6 | Lettering | `lettering` | `pages/*.png`, PDF | – |
| 7 | Review | `comic-review` | `review/sheet.png` | User bestätigt |
| 8 | Export | `lettering` | `pages/` | – |

Die Gates sind Pflicht. Ausnahme: Der User sagt ausdrücklich „mach durch“.

## Feste Regeln

1. **`comic.json` ist die einzige Wahrheit** (Figuren, Seiten, Panels, Blasen, Asset-Pfade, Status).
   Nach jeder Änderung `python3 tools/comic.py validate`. Nie Inhalte nur im HTML pflegen.
2. **Figuren über ihre id.** Story, `panel.cast` und `bubble.who` beziehen sich auf `cast[].id`.
   Das Aussehen steckt in der Referenz (`cast[].ref`) und in `look` – nicht in Panel-Prompts wiederholen.
3. **Kein Text im Bild.** Sprechblasen, Kästen, Soundwörter setzt `tools/layout.py`.
4. **Schau dir an, was du erzeugst** – Fotos, Figurvarianten, Panels, Seiten mit `Read`.
5. **Fotos echter Personen** nur mit deren Einverständnis; sie bleiben lokal (git-ignoriert).
6. **Lokal-first.** Eigene Rechner (lokal oder LAN/VPN) ja; keine Cloud-/Partner-Modelle
   (`partner_generate`, `confirm_spend=true`) ohne ausdrückliche Zustimmung.
7. Generierte Medien sind git-ignoriert; Text-Artefakte nach jeder Phase committen.

## Wichtige Pfade

- `tools/comic.py` (validate/show/formats/styles/layouts), `cast.py`, `panels.py`, `layout.py`
- `templates/styles.json` – Stil-Vorlagen; `templates/project/` – Vorlage für `comic/`
- `schemas/comic.schema.json` – Datenvertrag; `comfy/workflows/` – geprüfte Workflows
- `fonts/` – Lettering-Schriften (Comic Neue, Bangers; SIL OFL)

## Umgebung

- ComfyUI standardmäßig `http://127.0.0.1:8188`; anderer Rechner: `scripts/init.sh --comfy-url …`
  bzw. `.comgen.env` (aktive Adresse: `python3 tools/_common.py comfy-url`).
- Bild: **Z-Image Turbo**; Foto → Figur und Figurentausch: **Qwen Image 2.1 Turbo Edit**.
- Layout: Headless-Chrome (`python3 tools/_common.py chrome`), FFmpeg für Vergleichsbilder.
