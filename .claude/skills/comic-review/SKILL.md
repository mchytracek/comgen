---
name: comic-review
description: Qualitätskontrolle eines Comics – Seiten und Übersicht ansehen, Figurenähnlichkeit, Stilkonsistenz, Anschlussfehler, Lesefluss, Lettering und Druck-/Social-Tauglichkeit prüfen und Fehler beheben. Verwenden in Phase 7 des Comic-Workflows oder wenn fertige Seiten geprüft oder verbessert werden sollen.
---

# Comic-Review

```bash
python3 tools/layout.py && python3 tools/layout.py sheet
```

`comic/review/sheet.png` (alle Seiten) und jede Seite `comic/pages/<id>.png` mit `Read` ansehen;
für Details einzelne Panels (`comic/assets/panels/<id>.png`).

## Checkliste

1. **Figuren:** jede Figur in jedem Panel als dieselbe erkennbar (Gesicht, Frisur, Brille,
   Kleidung) und der Referenz ähnlich. Abweichung → `panels.py --only <id> --reswap`
   (ggf. `wear`/`expression` schärfen); falsche Person ersetzt → `where` präzisieren.
2. **Anschlüsse:** gleicher Ort sieht gleich aus, Requisiten bleiben, Tageszeit/Licht passen,
   Figuren stehen panelübergreifend auf derselben Seite (180°-Regel).
3. **KI-Fehler:** Hände, zusätzliche oder doppelte Personen, fremde statt Cast-Figuren, falsche
   Größenverhältnisse, fehlende Requisiten, Pseudotext im Bild → gezielt
   `panels.py edit <id> "…"` (bzw. `--ref <ids>`), sonst neuer `seed`/Prompt und `--force --only <id>`.
4. **Stil:** alle Panels im gleichen Stil; Ausreißer neu erzeugen.
5. **Lesefluss:** Blasenreihenfolge eindeutig, Zeiger am Mund, keine Blase über Gesicht/Handlung,
   Seitenwechsel-Momente sitzen am Seitenende.
6. **Text:** Rechtschreibung, ≤ 20 Wörter pro Blase, Namen und Fachbegriffe konsistent,
   Kernaussage am Ende klar, CTA vorhanden (Erklär-Comic).
7. **Ausgabe:** Druck – Wichtiges im Satzspiegel, PDF-Seitengröße inkl. Beschnitt;
   Social – auf Handygröße lesbar, eine Aussage pro Slide.

## Danach

Fehler selbst beheben (`comic.json` → `panels.py`/`layout.py`), neu rendern, erneut prüfen.
Erst dann dem User zeigen (**Gate**); verbleibende Kompromisse benennen. Status `review` → `done`.
