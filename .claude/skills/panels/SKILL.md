---
name: panels
description: Übersetzt die Comic-Story in das Seiten- und Panel-Skript in comic.json – Seitenraster, Einstellungen, Bildprompts, Figuren pro Panel, Sprechblasen, Erzählerkästen und Soundwörter. Verwenden in Phase 4 des Comic-Workflows oder wenn Seiten, Panels, Raster, Prompts oder Dialoge geändert werden.
---

# Seiten- & Panel-Skript

Eingabe: `story.md`, `comic.json → cast`. Ausgabe: `comic.json → pages`.
Nach jedem Schreiben: `python3 tools/comic.py validate` – prüft Raster ↔ Panelzahl, IDs, Figuren, Textmengen.

## Seite

```json
{ "id": "p02", "beat": "Aha-Moment", "layout": [[1, 1], [2, 1], [1]], "rows": [1, 1, 1.3], "panels": [ … ] }
```

- `layout`: Zeilen mit relativen Breiten **oder** ein benanntes Raster (`python3 tools/comic.py layouts`:
  `grid-6`, `classic-5`, `hero-top`, `strip-3`, `splash` …). Panels in Leserichtung, `id` = `p02-1`, `p02-2` …
- `rows`: relative Zeilenhöhen (größere Zeile = mehr Gewicht).
- `fullBleed: true` + 1 Panel: Cover/Splash über die ganze Seite inkl. Beschnitt.
- Abwechslung: nicht jede Seite gleich rastern; Schlüsselmoment = größtes Panel der Seite.
- Social: 1–3 Panels pro Slide, eine Aussage pro Slide; Strip: `strip-3`/`strip-4`.

## Panel

```json
{
  "id": "p02-3",
  "shot": "medium",
  "prompt": "an office desk with a laptop showing a dashboard with green checkmarks, morning light",
  "cast": [
    { "id": "anna", "where": "on the left", "action": "points at the laptop screen", "expression": "delighted" },
    { "id": "max", "where": "on the right", "expression": "proud grin" }
  ],
  "bubbles": [
    { "type": "speech", "who": "anna", "text": "Das hat er alles allein gebucht?", "pos": "tl" },
    { "type": "speech", "who": "max", "text": "In drei Sekunden.", "pos": "tr" }
  ]
}
```

- `shot`: `establishing`, `wide`, `full`, `medium`, `close`, `extreme-close`, `over-shoulder`, `bird`, `worm`.
  Wechseln! Seitenanfang oft `establishing`/`wide`, Emotion `close`.
- `prompt` (englisch): Ort, Handlung, Requisiten, Licht – **ohne** Figurenbeschreibung (die kommt
  aus `cast.look`) und **ohne Text im Bild** (Bildschirme: „showing a chart“, nie konkreten Text).
  Bei Figuren grob nennen, wer wo ist („a woman on the left and a man on the right“).
- `cast`: wer im Bild ist. Bei mehr als einer Figur **`where`** angeben – sonst weiß der
  Figurentausch nicht, wen er ersetzen soll. Max. 2–3 Figuren pro Panel; Hintergrundpersonen
  nur im `prompt`. `action`/`expression`/`wear` überschreiben Pose, Mimik, Kleidung.
- `seed`: optional (Default stabil aus der ID); neuer Seed = neues Bild.

## Blasen

| type | wofür | Hinweis |
|------|-------|---------|
| `speech` | Rede | `who` = cast-id; `"off"` = Stimme von außerhalb (kein Zeiger) |
| `thought` | Gedanke | Kreise statt Zeiger |
| `whisper` | Flüstern | gestrichelt |
| `shout` | Rufen | dicker Rand, Großbuchstaben |
| `caption` | Erzählerkasten | Zeit/Ort, Erklärung; oben links |
| `sfx` | Lautmalerei | `rot` = Drehung in Grad, `size` = Faktor |

- **Leserichtung:** Blasen in der Reihenfolge, in der gelesen wird – oben links vor rechts,
  oben vor unten. Wer zuerst spricht, steht links/oben (Figuren entsprechend platzieren).
- `pos`: `tl tc tr ml mc mr bl bc br` oder `{"x": 0.05, "y": 0.08, "w": 0.4}` (linke obere Ecke,
  Breite; Anteile des Panels). Endgültig platziert wird im Skill `lettering`, wenn die Bilder da sind.
- Text: ≤ 20 Wörter pro Blase, ≤ 45 pro Panel; `**Betonung**` wird fett, `\n` bricht um.

## Danach

`python3 tools/layout.py` rendert ein **Rohlayout** mit Platzhaltern → `comic/pages/*.png`
ansehen und dem User zeigen (Gate): Raster, Lesefluss, Textmengen. Status `panels`.
