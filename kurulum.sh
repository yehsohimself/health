#!/bin/bash
# PT install (macOS, Apple silicon). No sudo. Needs Homebrew (https://brew.sh) and Git.
# Kurulum (macOS, Apple işlemci). Sudo istemez; Homebrew ve Git gerekir.
set -e
cd "$(dirname "$0")"

echo "1/4 Tools via Homebrew: ffmpeg, uv"
if ! command -v brew >/dev/null; then echo "Homebrew not found. Install it first: https://brew.sh"; exit 1; fi
for p in ffmpeg uv; do brew list "$p" >/dev/null 2>&1 || brew install "$p"; done

echo "2/4 Python environment (.venv) and packages"
[ -d .venv ] || uv venv .venv --python 3.12
uv pip install --python .venv/bin/python --only-binary :all: -r requirements.txt

echo "3/4 Exercise pictures and coach voice (about 45 MB)"
mkdir -p pt kayitlar pt_medya
if [ ! -f pt_medya/.paket ]; then
  t="$(mktemp -d)/pt-medya.zip"
  if command -v gh >/dev/null && gh release download --repo yehsohimself/pt --pattern pt-medya.zip --output "$t" 2>/dev/null; then :
  elif curl -fsSL -o "$t" https://github.com/yehsohimself/pt/releases/latest/download/pt-medya.zip; then :
  else echo "   Pictures could not be downloaded; PT works without them. Run ./kurulum.sh again later."; t=""; fi
  if [ -n "$t" ]; then unzip -oq "$t" -d pt_medya && touch pt_medya/.paket; fi
fi

echo "4/4 Done. Start with:"
echo "    .venv/bin/python pt_sunucu.py"
echo "then open http://127.0.0.1:8771 (later: double-click PT.command)."
echo "Plans, meal estimates and coach messages need Claude Code signed in: claude auth login"
