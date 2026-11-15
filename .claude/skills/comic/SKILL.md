---
name: comic
description: Orchestriert die Produktion eines Comics mit ComfyUI – Briefing, Figuren aus Fotos, Story, Seiten-/Panel-Skript, Panel-Bilder, Lettering, Review und Export als PNG/PDF für Druck, Web oder Social. Verwenden, sobald der User einen Comic, Erklär-Comic, Comic-Strip oder Comic-Seiten erstellen, fortsetzen oder überarbeiten will („mach einen Comic über …“, „/comic“, „weiter mit dem Comic“).
---

# Comic-Orchestrator

Du führst einen Comic durch acht Phasen. Jede Phase hat einen eigenen Skill – lies ihn,
bevor du die Phase beginnst. Der Zustand liegt immer in `comic/comic.json`
(Feld `status`), damit die Produktion jederzeit fortgesetzt werden kann.

## 0. Stand feststellen

Dieses Repo ist **ein Comic** (Klon des comgen-Templates). Alles Comicspezifische liegt in `comic/`.

- `comic/` fehlt → Titel, Format, Stil, Zweck erfragen bzw. ableiten, dann
  `scripts/init.sh "<Titel>" [--format print-a4|print-us|print-a5-quer|web|social-4x5|social-1x1|social-9x16]
  [--style explainer|ligne-claire|us-comic|manga|graphic-novel] [--purpose explainer|story|product|social]
  [--comfy-url http://host:8188]`. `--comfy-url` nur, wenn der User einen anderen ComfyUI-Rechner nennt.
- `comic/` existiert → `python3 tools/comic.py show`; beim ersten offenen Schritt weitermachen.
- `server_info` (comfy-mcp) einmal aufrufen. Läuft ComfyUI nicht → Skill `comgen-setup`.
- Nach jeder Phase committen (`git add comic && git commit -m "<Phase>: …"`). Bilder, Seiten und
  Fotos sind git-ignoriert, `comic.json`, `brief.md`, `story.md` werden versioniert.

## 1. Briefing → `brief.md`

Eine Rückfrage-Runde (AskUserQuestion, max. 4 Fragen), nur was fehlt:
Zweck (Erklär-Comic, Story, Produkt, Social-Serie) · Ausgabe (Druck A4/US, Web, Social 4:5/1:1/9:16) ·
Umfang (Seiten bzw. Slides) · Zielgruppe & Kernbotschaft · Stil · **Figuren: wer, gibt es Fotos?** ·
Sprache/Tonalität · Branding. Defaults setzen und als „Annahme“ markieren.
Faustregeln Umfang: Erklär-Comic 2–6 Seiten; Social-Karussell 5–10 Slides; Strip 3–4 Panels.
→ **Gate:** Brief zusammenfassen, bestätigen lassen. Status `cast`.

## 2. Figuren (Skill `cast`) → **Gate**

Fotos übernehmen und automatisch in den Comicstil rendern (`tools/cast.py add`), Figuren ohne
Foto aus Beschreibung. Jede Figur bekommt `look` und `personality`. Vergleichsbilder **ansehen**
und dem User zeigen – die Figuren prägen den ganzen Comic. Status `story`.

## 3. Story (Skill `story`) → `story.md` → **Gate**

Bezieht sich auf die Figuren per Name/ID. Seitenweise Beats, Seitenwechsel-Momente.

## 4. Skript (Skill `panels`) → `comic.json` Seiten, Panels, Blasen → **Gate**

Danach sofort ein **Rohlayout** rendern (`python3 tools/layout.py` – Platzhalter statt Bilder)
und dem User zeigen: Seitenaufteilung und Textmengen sind so vor der teuren Bilderzeugung prüfbar.

## 5. Panel-Bilder (Skill `comfyui`)

Erst **ein** Panel mit Figur erzeugen und zeigen (Stil + Ähnlichkeit), dann den Rest:
`python3 tools/panels.py` (lange Läufe im Hintergrund). Jedes Bild ansehen.

## 6. Lettering & Layout (Skill `lettering`)

Blasen platzieren (Positionen, Zeiger auf die Münder), Seiten rendern.

## 7. Review (Skill `comic-review`) → **Gate**

## 8. Export

`python3 tools/layout.py` (+ `--pdf`), `python3 tools/layout.py sheet`. Status `done`.
Dem User nennen: Pfade (`comic/pages/*.png`, PDF), Format, offene Punkte.
Druck: PDF ist RGB mit Beschnitt – Druckerei nach Farbprofil fragen.

## Arbeitsweise

- Änderungswünsche zuerst in `comic.json`, dann nur betroffene Panels neu
  (`panels.py --only p02-3`), Text-/Blasenänderungen brauchen nur `layout.py`.
- Text **nie** ins Bild generieren – alles Lettering kommt aus `layout.py`.
- Fotos echter Personen nur mit deren Einverständnis; sie bleiben lokal.
