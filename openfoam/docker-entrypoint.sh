#!/bin/bash
# docker-entrypoint.sh
#
# Sources the OpenFOAM v2112 environment, then executes the command
# given as argument. The default command (in the Dockerfile) is
# `./Allrun`, which runs setFields and starts heleShawFoam.
#
# Note: we deliberately do NOT use `set -e`. OF's bashrc has a few
# commands that return non-zero exit codes for legitimate reasons
# (e.g. _foamAddLibAuto returns 1 when a library dir is missing).
# Treating those as fatal would abort the entrypoint before we get
# to OF. We rely on the explicit sanity checks below to fail loudly
# if OF didn't actually load.

OF_BASHRC="/usr/lib/openfoam/openfoam2112/etc/bashrc"
HELESH_BINARY="/opt/heleShawFoam"

if [ ! -f "$OF_BASHRC" ]; then
    echo "docker-entrypoint: ERROR: cannot find $OF_BASHRC" >&2
    echo "The base image may not be opencfd/openfoam-default:2112." >&2
    exit 1
fi

# Save and clear the entrypoint's $@ before sourcing, so that OF's
# bashrc (which forwards "$@" to config.sh/setup) doesn't try to
# interpret our CMD arguments as OF setup args.
ENTRYPOINT_ARGS=("$@")
set --
# shellcheck disable=SC1090
. "$OF_BASHRC"
# shellcheck disable=SC2206
set -- "${ENTRYPOINT_ARGS[@]}"

# Belt-and-braces: OF utilities like foamSystemCheck inspect $SHELL,
# which can be empty in a non-interactive session.
export SHELL="${SHELL:-/bin/bash}"

# Sanity checks: the OF utilities and our compiled solver must exist.
missing=0
for cmd in blockMesh setFields; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "docker-entrypoint: ERROR: '$cmd' not on PATH after sourcing OF" >&2
        missing=1
    fi
done
if [ ! -x "$HELESH_BINARY" ]; then
    echo "docker-entrypoint: ERROR: $HELESH_BINARY not found" >&2
    missing=1
fi
if [ "$missing" -ne 0 ]; then
    exit 1
fi

# Symlink the heleShawFoam binary into the user bin dir, so the
# case's Allrun can find it on PATH (it lives at /root/... in the
# base OF install, but we ship it at /opt/heleShawFoam and surface
# it into the PATH for the simulation).
mkdir -p /root/OpenFOAM/user-v2112/platforms/linux64GccDPInt32Opt/bin
ln -sf "$HELESH_BINARY" /root/OpenFOAM/user-v2112/platforms/linux64GccDPInt32Opt/bin/heleShawFoam

cd "${WORKDIR:-/case}"
exec "$@"
