FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg python3 python3-pip \
    && python3 -m pip install --no-cache-dir --break-system-packages "yt-dlp[default]" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json ./
COPY apps/api ./apps/api

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=8787

RUN useradd --create-home --uid 10001 beetales \
    && mkdir -p /tmp/beetales-downloads \
    && chown -R beetales:beetales /app /tmp/beetales-downloads

USER beetales
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:8787/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]
CMD ["node", "apps/api/src/index.mjs"]
