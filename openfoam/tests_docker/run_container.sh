#!/bin/sh
# run_container.sh
#
# Run the hele-shaw simulation inside the Docker container and save the
# solver log. The user can then run tests/compare.py against the saved
# log's output to verify a fresh run.
#
# Usage:
#   tests/run_container.sh                    # default: runs Allrun
#   tests/run_container.sh bash               # drops into a shell
#
# Side effects on the host:
#   testcase/log.heleShawFoam    - full solver log
#   testcase/<time-dirs>         - all generated time steps (in 0/, 0.05, ...)
#
# Requirements: the image must already be built (`docker build -t hele-shaw .`).

set -e

cd "$(dirname "$0")/.." || exit 1

IMAGE="${HELE_SHAW_IMAGE:-hele-shaw:latest}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "run_container.sh: image '$IMAGE' not found." >&2
    echo "  Build it first with: docker build -t hele-shaw ." >&2
    exit 1
fi

echo "run_container.sh: running '$IMAGE' on ./testcase ..."
docker run --rm \
    -v "$PWD/testcase:/case" \
    "$IMAGE" \
    "$@"

echo "run_container.sh: container exited. Inspect testcase/log.heleShawFoam for results."
