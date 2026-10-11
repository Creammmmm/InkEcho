FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    libglib2.0-0t64 libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
    fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen
ENV XDG_CACHE_HOME=/tmp/cache
USER 65532:65532
