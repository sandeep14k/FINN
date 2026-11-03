FROM node:22-bookworm-slim AS node
FROM python:3.13-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /app
COPY requirements.txt ./
RUN python -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY finn-app/package*.json ./finn-app/
RUN cd finn-app && npm ci
COPY . .
RUN cd finn-app && npm run build
ENV NODE_ENV=production FINN_ROOT=/app FINN_PYTHON=/app/venv/bin/python FINN_ENABLE_RESEARCH=1 FINN_ENRICH_FILINGS=0 FINN_MONITOR=1
WORKDIR /app/finn-app
EXPOSE 3000
CMD ["sh", "/app/start.sh"]
