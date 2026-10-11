FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    libglib2.0-0t64 libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libpulse0 \
    fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen
ENV XDG_CACHE_HOME=/tmp/cache
ENV XDG_CONFIG_HOME=/tmp/config
ENV XDG_DATA_HOME=/tmp/data
ENV XDG_STATE_HOME=/tmp/state
ENV XDG_RUNTIME_DIR=/tmp/runtime
USER 65532:65532
