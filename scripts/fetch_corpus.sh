#!/usr/bin/env bash
set -euo pipefail

# Fetches only the paragraph- and word-level XML sources from the
# bergson-synoptique corpus repo, using a partial + sparse checkout so we
# never download unrelated repo content or history.
#
# Uses HTTPS (not SSH) so this script runs for anyone on a public repo,
# without requiring the runner to have their own SSH key configured.
#
# Usage: ./scripts/fetch_corpus.sh

REPO_URL="https://github.com/johnloque/bergson-synoptique.git"
BRANCH="master"
TARGET_DIR="data/raw/corpus"
SPARSE_PATHS=("raw/src" "tag/src")

if [ -d "${TARGET_DIR}/.git" ]; then
  echo "Corpus already present in ${TARGET_DIR}, updating..."
  git -C "${TARGET_DIR}" fetch --depth 1 origin "${BRANCH}"
  git -C "${TARGET_DIR}" checkout "${BRANCH}"
  git -C "${TARGET_DIR}" reset --hard "origin/${BRANCH}"
  echo "Corpus updated."
  exit 0
fi

mkdir -p "${TARGET_DIR}"

git clone --filter=blob:none --no-checkout --depth 1 --branch "${BRANCH}" \
  "${REPO_URL}" "${TARGET_DIR}"

git -C "${TARGET_DIR}" sparse-checkout init --cone
git -C "${TARGET_DIR}" sparse-checkout set "${SPARSE_PATHS[@]}"
git -C "${TARGET_DIR}" checkout "${BRANCH}"

echo "Corpus fetched into ${TARGET_DIR} (paths: ${SPARSE_PATHS[*]})"