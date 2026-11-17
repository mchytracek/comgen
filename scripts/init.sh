#!/usr/bin/env bash
# Macht aus einem frischen Klon des Templates ein eigenes Comic-Repo und legt den ersten Comic
# in comics/01-<slug>/ an (comic ist ein Verweis auf den aktiven Comic).
# Weitere Comics im selben Repo: python3 tools/init_comic.py "<Titel>" [--from 01]
#
#   git clone https://github.com/mchytracek/comgen.git mein-comic && cd mein-comic
#   scripts/init.sh "Wie Rechnungen sich selbst buchen" [--format print-a4] [--style explainer] [--purpose explainer]
#
# Optionen (zusätzlich zu denen von tools/init_comic.py: --format, --style, --purpose, --lang, --slug):
#   --comfy-url URL ComfyUI-Server, z. B. http://gpu-box:8188 (Default: lokal 127.0.0.1:8188).
#                   Ohne Option wird interaktiv gefragt; Vorschlag = zuletzt gewählte Adresse.
#                   Gespeichert in .comgen.env (git-ignoriert) und ~/.config/comgen/env.
#   --keep-origin   origin NICHT in "template" umbenennen
#   --no-commit     nichts committen
# Formate: python3 tools/comic.py formats · Stile: python3 tools/comic.py styles
set -euo pipefail
cd "$(dirname "$0")/.."

keep_origin=0; commit=1; comfy_url=""; args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-origin) keep_origin=1 ;;
    --no-commit)   commit=0 ;;
    --comfy-url)   comfy_url="${2:?--comfy-url braucht eine URL}"; shift ;;
    --comfy-url=*) comfy_url="${1#*=}" ;;
    -h|--help)     sed -n 2,18p "$0"; exit 0 ;;
    *)             args+=("$1") ;;
  esac
  shift
done
[[ ${#args[@]} -ge 1 ]] || { sed -n 2,18p "$0"; exit 1; }

step() { printf "\n\033[1m▶ %s\033[0m\n" "$*"; }

lock_template_push() {
  # Ins Template wird nie gepusht: Upstream lösen und Push-URL sperren (Holen bleibt möglich)
  git branch --unset-upstream >/dev/null 2>&1 || true
  git remote set-url --push template "KEIN_PUSH_INS_TEMPLATE__eigenes_Remote_anlegen__git_remote_add_origin_URL"
}

if [[ -e comic ]] || compgen -G "comics/*/comic.json" >/dev/null; then
  echo "✖ Dieses Repo ist schon initialisiert. Weiterer Comic: python3 tools/init_comic.py \"<Titel>\" [--from 01]"
  exit 1
fi

step "ComfyUI-Server"
config_home="${COMGEN_CONFIG:-$HOME/.config/comgen}"
suggest=$(python3 tools/_common.py comfy-url)
if [[ -z "$comfy_url" ]]; then
  if [[ -t 0 ]]; then
    read -r -p "  ComfyUI-URL [$suggest]: " comfy_url || true
  else
    echo "  (nicht interaktiv – nutze $suggest; ändern mit --comfy-url)"
  fi
fi
comfy_url="${comfy_url:-$suggest}"
[[ "$comfy_url" == *://* ]] || comfy_url="http://$comfy_url"
comfy_url="${comfy_url%/}"
if [[ "$comfy_url" != http://* ]] || [[ "${comfy_url#http://}" == */* ]]; then
  echo "  ✖ Nur http://host:port ohne Pfad wird unterstützt (comfy-cli/comfy-mcp): $comfy_url"; exit 1
fi
printf '# ComfyUI-Server dieses Comic-Repos (von scripts/init.sh, git-ignoriert)\nCOMFYUI_URL=%s\n' "$comfy_url" > .comgen.env
mkdir -p "$config_home"
printf '# Vorschlag für scripts/init.sh (zuletzt gewählter ComfyUI-Server)\nCOMFYUI_URL=%s\n' "$comfy_url" > "$config_home/env"
if curl -s -m 5 "$comfy_url/system_stats" | grep -q comfyui_version; then
  echo "  ✔ $comfy_url erreichbar"
else
  echo "  ⚠ $comfy_url antwortet nicht – läuft ComfyUI dort mit --listen? (später: scripts/doctor.sh)"
fi

step "Comicordner anlegen"
python3 tools/init_comic.py "${args[@]}"

if git rev-parse --git-dir >/dev/null 2>&1; then
  if [[ $keep_origin == 0 ]] && git remote get-url origin >/dev/null 2>&1 \
     && ! git remote get-url template >/dev/null 2>&1; then
    step "Git: origin → template (für spätere Template-Updates)"
    git remote rename origin template
    lock_template_push
    echo "  Template-Updates holen:   scripts/update-template.sh"
    echo "  Eigenes Remote anlegen:   git remote add origin <url> && git push -u origin HEAD"
  fi
  if [[ $commit == 1 ]]; then
    title=$(python3 -c 'import json;print(json.load(open("comic/comic.json"))["title"])')
    git add comics
    git commit -q -m "Comic initialisiert: $title" && echo "  ✔ commit: Comic initialisiert: $title"
  fi
fi

step "Umgebung prüfen"
scripts/doctor.sh || true

cat <<'EOF'

Fertig. Jetzt Claude Code in diesem Ordner starten und z. B. sagen:
  /comic Erklär-Comic, 4 Seiten A4: wie unsere Software Rechnungen automatisch bucht.
         Hauptfigur ist Anna (Foto: ~/Desktop/anna.jpg).
EOF
