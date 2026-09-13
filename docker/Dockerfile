FROM ros:jazzy-ros-base-noble@sha256:386d06ec6d4188f731bae5678e07b4cb64a4e4d4152090c0bd1f881dcf7706f5

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Resolve the only additional OS dependency against a fixed Ubuntu snapshot.
# The ROS installation is already supplied by the immutable base image.
COPY docker/ubuntu.sources /etc/apt/m0-ubuntu.sources
RUN apt-get -o Dir::Etc::sourcelist=/etc/apt/m0-ubuntu.sources \
        -o Dir::Etc::sourceparts=- update \
    && apt-get -o Dir::Etc::sourcelist=/etc/apt/m0-ubuntu.sources \
        -o Dir::Etc::sourceparts=- install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Existing standard action interfaces used by the real M4 transport tests.
ARG ROS_EXAMPLE_INTERFACES_VERSION=0.12.1-1noble.20260902.030327
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        "ros-jazzy-example-interfaces=${ROS_EXAMPLE_INTERFACES_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/agent-framework-venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}" \
    HOME=/home/developer \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System site packages make the image's apt-provided rclpy available to Python.
RUN python3 -m venv --system-site-packages "${VIRTUAL_ENV}"
COPY docker/requirements-dev.txt /opt/requirements-dev.txt
RUN python -m pip install --require-hashes -r /opt/requirements-dev.txt

WORKDIR /workspace/project
COPY agent-framework/ agent-framework/
COPY bindings/test/ bindings/test/
RUN python -m pip install --no-build-isolation --no-deps -e ./agent-framework \
    && python -m pip install --no-build-isolation --no-deps -e ./bindings/test \
    && python -m pip check

COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/project-entrypoint

# Match the WSL user so generated artifacts on the bind mount remain user-owned.
ARG DEV_UID=1000
ARG DEV_GID=1000
RUN mkdir -p /home/developer \
    && chown -R "${DEV_UID}:${DEV_GID}" /home/developer "${VIRTUAL_ENV}" /workspace/project
USER ${DEV_UID}:${DEV_GID}

ENTRYPOINT ["/usr/local/bin/project-entrypoint"]
CMD ["bash"]
