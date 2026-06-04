# Dockerfile for the hele-shaw-cells Hele-Shaw viscous-fingering demo.
#
# Uses the official opencfd/openfoam-default:2112 image as a base.
# This is a pre-built OpenFOAM-v2112 image that ships the full source
# tree, headers, and the wmake build system — so we only need to
# compile our custom heleShawFoam solver (~30 s) on top.
#
# Why this base image:
#   - Official OpenCFD image, multi-arch (amd64 + arm64)
#   - 1.82 GB on disk, 392 MB compressed
#   - Pull time: ~30 s on a fast link
#   - Source tree present at /usr/lib/openfoam/openfoam2112
#   - wmake, blockMesh, setFields, all utilities pre-built
#   - CentOS-7 based, EOL but works fine in containers
#
# The original `hele-shaw-cells/` upstream repo was built and tested
# against OF-v2112, and the Make/options and headers all match this
# version. There is no need to rebuild OF from source.
#
# Build (from this directory, i.e. openfoam/):
#   docker build -t hele-shaw .
#
# Run:
#   docker run --rm -v "$PWD/results/<config>:/case" hele-shaw
#
# The case is mounted at /case; the entrypoint sources the OF env and
# runs ./Allrun by default. See ../../docs/hele-shaw-cells.md for the
# full workflow description.

FROM opencfd/openfoam-default:2112

# The base image's /openfoam/run entrypoint expects a `command` arg
# and sources the OF environment before exec'ing it. We override
# it with our own entrypoint that runs ./Allrun by default.
# We need to be root to write into /opt and install packages.
USER root

# SHELL must be set so OF's foamSystemCheck recognises the runtime
# shell (the default Docker RUN shell is /bin/sh, which OF rejects).
SHELL ["/bin/bash", "-lc"]
ENV SHELL=/bin/bash \
    WM_PROJECT_VERSION=v2112 \
    FOAM_API=2112

# Compile our heleShawFoam solver against the pre-built OF.
# solver/ is the heleShawFoam source tree (heleShawFoam.C, *.H, Make/).
COPY solver/ /tmp/heleShawFoam/
RUN bash -lc "source /usr/lib/openfoam/openfoam2112/etc/bashrc && cd /tmp/heleShawFoam && wmake 2>&1 | tee /tmp/wmake-heleShaw.log"

# Install the heleShawFoam binary at a stable path on the base image
# (it was built to /root/OpenFOAM/user-v2112/.../bin/heleShawFoam by
# default; we copy it to /opt/heleShawFoam so the runtime image
# doesn't depend on /root/ in the user's mount).
RUN cp /root/OpenFOAM/user-v2112/platforms/linux64GccDPInt32Opt/bin/heleShawFoam /opt/heleShawFoam \
    && chmod +x /opt/heleShawFoam \
    && rm -rf /tmp/heleShawFoam /tmp/wmake-heleShaw.log

# Default working directory: the testcase mount point.
WORKDIR /case

# Entry point: source the OF env, then run ./Allrun (or whatever
# the user passed). The OF env is loaded via the same `source` path
# that wmake used.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["./Allrun"]
