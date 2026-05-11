#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_ROOT="${REPO_ROOT}/04_modeling_experimental/data/raw/brightlands"
SOURCE_2024="/Users/louis.ferger-andrews/Desktop/2024"
SOURCE_2025="/Users/louis.ferger-andrews/Desktop/2025"

mkdir -p "${TARGET_ROOT}/2024" "${TARGET_ROOT}/2025"

if [[ -d "${SOURCE_2024}" ]]; then
  rsync -a --delete "${SOURCE_2024}/" "${TARGET_ROOT}/2024/"
  echo "Synced: ${SOURCE_2024} -> ${TARGET_ROOT}/2024"
else
  echo "Skip (missing): ${SOURCE_2024}"
fi

if [[ -d "${SOURCE_2025}" ]]; then
  rsync -a --delete "${SOURCE_2025}/" "${TARGET_ROOT}/2025/"
  echo "Synced: ${SOURCE_2025} -> ${TARGET_ROOT}/2025"
else
  echo "Skip (missing): ${SOURCE_2025}"
fi
