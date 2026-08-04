#!/usr/bin/env bash
set -euo pipefail

UV_REQUIRED_VERSION="0.11.29"
EXCLUDE_NEWER="2026-08-04T00:00:00Z"
output_path="${1:-requirements/ci.lock}"

observed_version="$(uv --version | awk '{print $2}')"
if [ "$observed_version" != "$UV_REQUIRED_VERSION" ]; then
  printf 'compile_ci_lock: uv %s is required; found %s\n' \
    "$UV_REQUIRED_VERSION" "${observed_version:-missing}" >&2
  exit 2
fi

mkdir -p "$(dirname "$output_path")"
uv pip compile requirements/ci.in \
  --universal \
  --python-version 3.10 \
  --generate-hashes \
  --exclude-newer "$EXCLUDE_NEWER" \
  --no-header \
  --output-file "$output_path"
