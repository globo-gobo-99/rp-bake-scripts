# syntax=docker/dockerfile:1
ARG UBUNTU_IMAGE=ubuntu:24.04
FROM ${UBUNTU_IMAGE} AS common
ENV DEBIAN_FRONTEND=noninteractive LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 TZ=Etc/UTC
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates openssh-server supervisor tini sudo locales tzdata vim git tmux less man-db findutils file tree ripgrep jq curl wget rsync unzip zip xz-utils bzip2 procps htop lsof iproute2 net-tools dnsutils iputils-ping build-essential python3 python3-venv python3-pip docker.io caddy nginx && locale-gen en_US.UTF-8 && rm -rf /var/lib/apt/lists/* && (userdel ubuntu || true) && useradd --uid 1000 --no-create-home --home-dir /workspace/home/dev --shell /bin/bash dev && passwd -d dev
COPY shared/tools.lock.json /opt/devpod/tools.lock.json
COPY shared/npm/ /opt/devpod/npm/
COPY container-template/ /opt/devpod/
COPY --chmod=644 container-template/env /etc/devpod-env
RUN chmod -R a+rX /opt/devpod && mkdir -p /usr/local/lib/docker/cli-plugins && ln -s /workspace/toolchains/current/bin/docker-buildx /usr/local/lib/docker/cli-plugins/docker-buildx && printf 'source /etc/devpod-env\n' > /etc/profile.d/devpod.sh && chmod +x /opt/devpod/start.sh /opt/devpod/devpod-* && ln -s /opt/devpod/devpod-install-vscode /usr/local/bin/devpod-install-vscode && ln -s /opt/devpod/devpod-enable-sync /usr/local/bin/devpod-enable-sync && mkdir -p /workspace && printf 'dev ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/dev && chmod 440 /etc/sudoers.d/dev
EXPOSE 22
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/devpod/start.sh"]
FROM common AS testpod
RUN python3 /opt/devpod/install-tools.py --runtime-only
ENV PATH=/opt/devpod/seed/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN python3 /opt/devpod/manifest.py --role testpod
FROM common AS devpod
RUN python3 /opt/devpod/install-tools.py
ENV PATH=/opt/devpod/seed/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN python3 /opt/devpod/manifest.py
