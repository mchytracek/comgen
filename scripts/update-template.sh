#!/usr/bin/env bash
# Holt Verbesserungen aus dem Template-Repo (Skills, Tools, Workflows) in dieses Comic-Repo.
# Die Comics (comics/, Verweis comic) existieren im Template nicht, daher gibt es dort keine Konflikte.
# Ältere Klone mit einem echten Ordner comic/ werden dabei nach comics/01-<slug>/ umgezogen.
#
#   scripts/update-template.sh            # Remote "template", Branch main
#   scripts/update-template.sh <branch>
set -euo pipefail
cd "$(dirname "$0")/.."
branch="${1:-main}"

git remote get-url template >/dev/null 2>&1 || {
  echo "Kein Remote 'template'. Anlegen mit: git remote add template <template-url>"; exit 1; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "Arbeitskopie hat uncommittete Änderungen – erst committen oder stashen."; exit 1; }

git fetch template "$branch"
echo "Neu im Template:"
git log --oneline "HEAD..template/$branch" || true
git merge --no-edit "template/$branch"
python3 tools/comic.py list   # zieht ein altes comic/ nach comics/ um (danach committen)
echo "✔ Template-Stand übernommen. Claude Code neu starten, falls Skills/MCP geändert wurden."
