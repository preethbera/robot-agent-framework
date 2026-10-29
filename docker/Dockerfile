FROM ros:jazzy-ros-base-noble@sha256:386d06ec6d4188f731bae5678e07b4cb64a4e4d4152090c0bd1f881dcf7706f5 AS dev

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Resolve the only additional OS dependency against a fixed Ubuntu snapshot.
# The ROS installation is already supplied by the immutable base image.
COPY docker/ubuntu.sources /etc/apt/project-ubuntu.sources
RUN apt-get -o Dir::Etc::sourcelist=/etc/apt/project-ubuntu.sources \
        -o Dir::Etc::sourceparts=- update \
    && apt-get -o Dir::Etc::sourcelist=/etc/apt/project-ubuntu.sources \
        -o Dir::Etc::sourceparts=- install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Existing standard action interfaces used by the real ROS2 transport tests.
ARG ROS_EXAMPLE_INTERFACES_VERSION=0.12.1-1noble.20260911.054159
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        "ros-jazzy-example-interfaces=${ROS_EXAMPLE_INTERFACES_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/agent-framework-venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}" \
    HOME=/home/developer \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System site packages make the image's apt-provided rclpy available to Python.
RUN python3 -m venv --system-site-packages "${VIRTUAL_ENV}"
COPY docker/requirements-dev.txt /opt/requirements-dev.txt
RUN python -m pip install --require-hashes -r /opt/requirements-dev.txt

WORKDIR /workspace/project
COPY agent-framework/ agent-framework/
COPY bindings/ bindings/
RUN python -m pip install --no-build-isolation --no-deps ./agent-framework \
    && for binding in ./bindings/*/; do \
        if [ -f "${binding}pyproject.toml" ]; then \
            python -m pip install --no-build-isolation --no-deps "$binding"; \
        fi; \
    done \
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


# PX4 stage extends the development image with external simulation and SITL firmware
FROM dev AS px4
USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY docker/px4-versions.env /opt/px4-versions.env
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential cmake ninja-build libeigen3-dev libxml2-utils libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install empy==3.3.4 pyros-genmsg==0.5.8 kconfiglib==14.1.0 \
    jinja2==3.1.6 MarkupSafe==3.0.3 PyYAML==6.0.3 numpy==2.2.6 \
    jsonschema==4.25.1 sympy==1.14.0 packaging==26.3

# External ROS dependency workspace, never under /workspace/project.
RUN source /opt/px4-versions.env \
    && git clone --depth 1 --branch "$PX4_MSGS_TAG" https://github.com/PX4/px4_msgs.git /tmp/px4-interfaces/src/px4_msgs \
    && test "$(git -C /tmp/px4-interfaces/src/px4_msgs rev-parse HEAD)" = "$PX4_MSGS_COMMIT" \
    && source /opt/ros/jazzy/setup.bash \
    && cd /tmp/px4-interfaces \
    && colcon build --merge-install --install-base /opt/px4/ros \
        --cmake-args -DBUILD_TESTING=OFF -DPython3_EXECUTABLE=/usr/bin/python3 \
    && rm -rf /tmp/px4-interfaces
RUN source /opt/px4-versions.env \
    && git clone --depth 1 --branch "$XRCE_AGENT_TAG" https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /tmp/xrce-agent \
    && test "$(git -C /tmp/xrce-agent rev-parse HEAD)" = "$XRCE_AGENT_COMMIT" \
    && cmake -S /tmp/xrce-agent -B /tmp/xrce-agent/build -DCMAKE_INSTALL_PREFIX=/opt/px4/xrce \
    && cmake --build /tmp/xrce-agent/build -j2 \
    && cmake --install /tmp/xrce-agent/build \
    && rm -rf /tmp/xrce-agent
RUN source /opt/px4-versions.env \
    && git clone --depth 1 --branch "$PX4_TAG" \
        https://github.com/PX4/PX4-Autopilot.git /opt/px4/firmware \
    && test "$(git -C /opt/px4/firmware rev-parse HEAD)" = "$PX4_COMMIT" \
    && git -C /opt/px4/firmware submodule update --init --recursive --depth 1 -- \
        src/drivers/gps/devices src/lib/events/libevents src/lib/heatshrink/heatshrink \
        src/modules/mavlink/mavlink src/modules/uxrce_dds_client/Micro-XRCE-DDS-Client
RUN cd /opt/px4/firmware && make -j2 px4_sitl_default

ENV PATH="/opt/px4/xrce/bin:${PATH}" LD_LIBRARY_PATH="/opt/px4/xrce/lib"
USER 1000:1000
ENTRYPOINT ["/usr/local/bin/project-entrypoint"]
CMD ["bash"]
