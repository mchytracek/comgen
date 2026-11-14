---
name: cast
description: Legt die Figuren eines Comics an – Fotos von Personen hochladen und automatisch im Comicstil rendern (Qwen Image Edit), Figuren ohne Foto aus einer Beschreibung erzeugen, Referenz wählen, Aussehen und Wesen festhalten. Verwenden in Phase 2 des Comic-Workflows oder wenn Figuren hinzukommen, ausgetauscht oder neu gerendert werden sollen.
---

# Figuren (Cast)

Jede Figur hat in `comic.json → cast` eine **id** (klein, ohne Leerzeichen: `anna`,
`chef-mueller`). Story, Panels (`panel.cast`) und Sprechblasen (`bubble.who`) beziehen
sich nur auf diese id.

## Foto → Comicfigur

Der User gibt einen Dateipfad (Drag & Drop ins Terminal) oder legt das Foto nach `comic/cast/`.

```bash
python3 tools/cast.py add anna ~/Desktop/anna.jpg --name "Anna" --role "Buchhalterin, Hauptfigur" \
  --look "woman in her thirties, shoulder-length wavy auburn hair, round glasses, mustard cardigan"
```

1. **Vorher das Foto mit `Read` ansehen** und `--look` selbst schreiben (englisch, 10–25 Wörter:
   Alter, Haare, Gesicht/Brille/Bart, Kleidung mit Farben). `look` steuert den Bildaufbau jedes Panels.
2. `add` kopiert das Foto nach `comic/cast/anna/photo.*`, rendert 3 Varianten im Stil
   `style.castStyle` und übernimmt Variante 1 **vorläufig** als Referenz (`refProvisional`).
3. Vergleich ansehen: `comic/review/cast/anna/grid.png` (Foto links). Kriterien: erkennbar
   (Gesichtsform, Frisur, Brille, Kleidung), sauber im Stil, ganze Figur sichtbar, keine Zusatzobjekte.
4. **Gate:** Raster dem User zeigen, Wahl abfragen → `python3 tools/cast.py pick anna 2`.
   Keine passt → `cast.py render anna --seeds 4,5,6` (oder `--waist-up`, `--prompt "…"`).

Gutes Foto: Person allein, Gesicht frontal und scharf, gleichmäßiges Licht, ganze Figur oder
mindestens Oberkörper. Kleine Handyfotos werden automatisch hochskaliert.

## Figur ohne Foto

```bash
python3 tools/cast.py add max --name "Max" --role "IT-Kollege" \
  --look "lanky man in his 30s, curly brown hair, round glasses, green hoodie, sneakers"
```

Z-Image erzeugt Varianten aus der Beschreibung; sonst wie oben (ansehen, `pick`).

## Wesen festhalten

Pro Figur in `comic.json` von Hand ergänzen: `personality` (2–3 Stichworte + Sprechweise,
z. B. „gewissenhaft, trocken-humorvoll; kurze Sätze“). Die Story und die Dialoge richten sich danach.

## Regeln

- Fotos echter Personen nur mit deren **Einverständnis**; sie bleiben lokal (git-ignoriert).
  Keine Personen des öffentlichen Lebens ohne ausdrücklichen Auftrag und Rechteklärung.
- Wechselt die Referenz einer Figur, müssen ihre Panels neu: `cast.py pick` nennt die
  betroffenen Panels (`panels.py --only … --reswap`).
- Stil erst festlegen, dann Figuren rendern – ein Stilwechsel macht alle Referenzen ungültig.
- `python3 tools/cast.py list` zeigt den Stand.
