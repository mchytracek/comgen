---
name: lettering
description: Setzt die Comic-Seiten – Sprechblasen platzieren, Zeiger auf die Sprecher richten, Erzählerkästen und Soundwörter, Seiten als PNG und PDF für Druck, Web und Social rendern. Verwenden in Phase 6/8 des Comic-Workflows oder wenn Blasen, Texte, Schriften oder der Export geändert werden.
---

# Lettering & Layout

Alles Lettering kommt aus `tools/layout.py` (HTML → Headless-Chrome), nie aus dem Bildmodell.
Schriften: Comic Neue (Dialog), Bangers (Soundwörter) aus `fonts/` (OFL); Fallback Comic Sans MS.

```bash
python3 tools/layout.py                 # alle Seiten → comic/pages/<id>.png (+ PDF bei Druckformaten)
python3 tools/layout.py --page p02      # eine Seite
python3 tools/layout.py --pdf           # PDF auch für Web/Social
python3 tools/layout.py sheet           # Übersicht → comic/review/sheet.png
```

## Blasen platzieren (wenn die Panel-Bilder da sind)

1. Seite rendern und ansehen. Für jedes Panel mit Dialog: `python3 tools/panels.py grid p02-3`
   → `comic/review/grid/p02-3.png` (Raster 5/10/50 %) ansehen.
2. **Zeiger:** `tail: {"x": …, "y": …}` auf den **Mund** der sprechenden Figur (Anteile des Panels).
   Ohne Angabe zeigt der Zeiger nur nach unten – bei Dialog immer setzen.
3. **Position:** Blasen in freie, ruhige Bildbereiche (Himmel, Wand, Boden), nie über Gesichter,
   Hände oder das, worum es im Panel geht. `pos: {"x", "y", "w"}` für Feinplatzierung.
4. **Leserichtung:** erste Blase oben links; der Blick wandert Z-förmig. Zeiger kreuzen sich nicht.
5. Seite neu rendern, prüfen, wiederholen. Nur `comic.json` ändern – nie das HTML.

## Formate

| Format | Ausgabe | Hinweise |
|--------|---------|----------|
| `print-a4`, `print-us`, `print-a5-quer` | PNG 300 dpi + PDF mit 3 mm Beschnitt | Wichtiges ≥ 12 mm vom Rand (Satzspiegel); Seitenzahlen automatisch (`pageNumbers: false` schaltet ab); PDF ist RGB – Druckerei nach Farbprofil fragen |
| `web` | PNG 1600×2400 | |
| `social-4x5`, `social-1x1`, `social-9x16` | PNG je Slide | größere Schrift; 9:16: oben/unten ~12 % frei lassen (UI-Overlays) |

Schriftgröße global: `style.lettering.size` (% der Seitenbreite), Großbuchstaben-Lettering:
`style.lettering.uppercase: true`. Farben: `style.palette` (`paper`, `ink`, `caption`, `accent`).
Bildausschnitt eines Panels verschieben: `panel.focus: {"x": 0.5, "y": 0.3}`.

## Prüfen

Lesbar in Zielgröße? (Social: Seite auf Handygröße verkleinert ansehen.) Text nicht abgeschnitten,
Blasen nicht über Panelränder gequetscht, Zeiger enden am Mund, Reihenfolge eindeutig.
