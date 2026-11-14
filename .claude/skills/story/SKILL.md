---
name: story
description: Entwickelt die Story eines Comics aus Briefing und Figuren – Kernaussage, Erzählbogen, Beats pro Seite, Seitenwechsel-Momente und Dialogideen, bezogen auf die Figuren im Cast. Verwenden in Phase 3 des Comic-Workflows oder wenn an Handlung, Pointe, Figurenrollen oder Seitenstruktur gearbeitet wird.
---

# Story

Eingabe: `comic/brief.md`, `comic.json → cast` (Namen, Rollen, `personality`).
Ausgabe: `comic/story.md`.

## Vorgehen

1. **Eine Kernaussage** in einem Satz („Nach dem Lesen weiß man, dass …“).
2. **Figuren aus dem Cast besetzen** – mit Namen, nie „eine Frau“. Jede Figur braucht eine
   Funktion (Held/in mit Problem, Helfer/in, Skeptiker/in). Wer nicht gebraucht wird, fliegt raus.
3. **Bogen wählen:**
   - Erklär-Comic: *Alltagsproblem → Frust → Begegnung mit der Lösung → Aha (wie es funktioniert,
     in 2–3 sichtbaren Schritten) → Ergebnis/Pointe → Handlung (CTA)*.
   - Story: *Ausgangslage → Störung → Zuspitzung → Wendepunkt → Auflösung*.
   - Strip / Social: *Setup → Entwicklung → Pointe* (Pointe im letzten Panel bzw. Slide).
4. **Seiten planen** – die Seite ist die Einheit des Comics:
   - Jede rechte Seite (Druck) bzw. jeder Slide (Social) endet mit einem Grund weiterzublättern
     (Frage, Überraschung, Cliffhanger). Große Enthüllungen auf eine **neue** Seite links oben.
   - Druck A4: 4–7 Panels pro Seite; Web: 3–6; Social-Slide: 1–3 große Panels.
   - Erklärteil: ein Schritt pro Panel, zeigen statt erzählen (Figur *tut* etwas mit dem Produkt).
5. **Dialoge skizzieren** – Comic ist Kurzform:
   - Max. **20 Wörter pro Blase**, max. 2 Blasen pro Figur und Panel, ≤ 45 Wörter pro Panel.
   - Erklärender Text in Erzählerkästen (caption) knapp halten; lieber eine Figur fragen lassen.
   - Sprechweise aus `personality`; Fachbegriffe beim ersten Mal erklären.
   - Lautmalerei (sfx) sparsam und gezielt.

## Format von `story.md`

```markdown
# <Titel>
**Kernaussage:** …   **Bogen:** …   **Umfang:** 4 Seiten A4
**Figuren:** anna (Heldin, Buchhalterin), max (Helfer, IT)

| Seite | Beat | Was passiert (Panels grob) | Wer | Seitenwechsel |
|-------|------|----------------------------|-----|---------------|
| 1 | Problem | Anna vor Papierbergen; Stapel kippt; Max taucht auf | anna, max | „Zeig mal!“ |
```

Darunter die wichtigsten Dialogzeilen je Seite. Dem User Kernaussage, Pointe und Seitenzahl
zeigen und Feedback einholen (**Gate**). Fakten/Zahlen mit Quelle in `## Quellen`.
