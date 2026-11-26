FROM debian:trixie-slim
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends prusa-slicer=2.9.2+dfsg-1 python3 \
    && rm -rf /var/lib/apt/lists/*
ENV HOME=/tmp XDG_CACHE_HOME=/tmp OMP_NUM_THREADS=2
WORKDIR /output
ENTRYPOINT ["prusa-slicer"]
