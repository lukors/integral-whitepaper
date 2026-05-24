#!/usr/bin/env bash
set -euo pipefail

if ! command -v gladtex >/dev/null 2>&1; then
  echo "gladtex is required to render EPUB math as SVG. Install it with: sudo apt install gladtex" >&2
  exit 127
fi

export GLADTEX_ARGS="${GLADTEX_ARGS:--d _book/gladtex-math -R}"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL_GLADTEX:-en_US.UTF-8}"

# Upstream issues causes many warnings,
# this line supresses them.
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::RuntimeWarning:subprocess}"
exec gladtex
