FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    --no-install-recommends ca-certificates qemu-system-x86 qemu-utils \
    genisoimage openssh-client python3 && rm -rf /var/lib/apt/lists/*

USER 1000:1000
