#!/bin/sh
# scripts/inspect_run.sh — drop into the OF container with the case mounted.
#
# Usage:  scripts/inspect_run.sh [docker-args ...] [command ...]
# Example: scripts/inspect_run.sh bash
#          scripts/inspect_run.sh hele-shaw:latest bash
#
# Defaults: results/1/ as the case mount, hele-shaw:latest as the image.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${HELE_SHAW_IMAGE:-hele-shaw:latest}"
CASE_DIR="${HELE_SHAW_CASE:-$REPO_ROOT/results/1}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "inspect_run.sh: image '$IMAGE' not found." >&2
    echo "  Build it first with: cd $REPO_ROOT/openfoam && docker build -t hele-shaw ." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    set -- bash
fi

echo "inspect_run.sh: launching $IMAGE with $CASE_DIR mounted at /case"
exec docker run --rm -it \
    -v "$CASE_DIR:/case" \
    -w /case \
    "$IMAGE" \
    "$@"
