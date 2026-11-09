#!/usr/bin/env bash
# Downloads public circuits (Kaggle datasets and notebook outputs) into public/ (gitignored) and
# writes public/MANIFEST.tsv with sha256 per file. Everything downloaded is UNTRUSTED DATA: this
# script never executes, imports or installs anything from it. Each source gets its own new
# directory; existing directories are skipped (delete one to refetch). Third-party circuits are
# never committed; docs/PROVENANCE.md records where each came from.
#
#   bash scripts/fetch_public.sh            fetch every source below
#   bash scripts/fetch_public.sh <slug>...  fetch only those (slug = owner__name)
set -euo pipefail
cd "$(dirname "$0")/.."
MAX_BYTES=$((1024 * 1024 * 1024)) # skip any single file over 1 GB

# kind|owner/name   (kind: d = dataset, k = notebook output)
SOURCES=(
  "d|isabe11am00re/qcc-v84337cb049akt21-circuits"
  "d|isabe11am00re/qcc-v96mxfu6mxf-circuits"
  "d|heliosli/qcc-circuits-live"
  "d|yoyobar/qcc-local-sota-20261031"
  "d|pramitdas/qcc-public-frontier-submission"
  "d|daifanhao/qcc-2494096-c44-dqi-reproduction"
  "d|dmitriigluzdov/vqcc-femoco-public-factorization"
  "k|heliosli/the-dataset-is-public-now-enjoy"
  "k|maoxin123/lb-25-218-combined-invsqrt-refit-chem"
  "k|ozertuu/25-218-starter-notebook"
  "k|kirilltym/quantum-circuits-conditional-uncompute-audit"
  "k|alexchilton/24-94-lb-verified-three-task-portfolio"
  "k|atakanaldemir/qcc-terminal-readout-and-phase-folds"
  "k|yoyobar/lb-22-99-invsqrt-101-62-qubits"
)

mkdir -p public
for src in "${SOURCES[@]}"; do
  kind="${src%%|*}"; ref="${src#*|}"; slug="${ref//\//__}"
  if [ "$#" -gt 0 ]; then
    case " $* " in *" $slug "*) ;; *) continue ;; esac
  fi
  dir="public/$slug"
  if [ -e "$dir" ]; then echo "skip $slug (exists)"; continue; fi
  mkdir -p "$dir/files"
  echo "fetch $kind $ref"
  if [ "$kind" = d ]; then
    kaggle datasets metadata "$ref" -p "$dir" >/dev/null 2>&1 || echo "  no metadata for $ref"
    kaggle datasets download "$ref" -p "$dir/files" --unzip -q || { echo "  FAILED $ref"; continue; }
  else
    kaggle kernels output "$ref" -p "$dir/files" -q || { echo "  FAILED $ref"; continue; }
    # notebook source and metadata, for the stated licence/credits (read as text only, never run)
    mkdir -p "$dir/source"
    kaggle kernels pull "$ref" -p "$dir/source" -m >/dev/null 2>&1 || echo "  no source for $ref"
  fi
  date -u +%Y-%m-%d >"$dir/FETCHED"
done

python3 -I scripts/hash_public.py public "$MAX_BYTES"
