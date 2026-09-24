# syntax=docker/dockerfile:1
# ----------------------------------------------------------------------------
# Frontend image — two stages:
#   1. node build : typecheck + production bundle (Vite)
#   2. nginx      : serve the static SPA with SPA-safe routing and caching
#
# Only public configuration (VITE_*) is passed as build args — never secrets.
# The container is only reachable on the internal network; the edge proxy
# (nginx service) publishes the host ports.
# ----------------------------------------------------------------------------

# --- Stage 1: build ---------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies from the lockfile first (better layer caching).
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# Build-time public configuration
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_APP_ENV=production
ARG VITE_APP_NAME=WIMS
ARG VITE_HEALTH_POLL_MS=30000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_ENV=${VITE_APP_ENV} \
    VITE_APP_NAME=${VITE_APP_NAME} \
    VITE_HEALTH_POLL_MS=${VITE_HEALTH_POLL_MS}

COPY . .
RUN npm run build

# --- Stage 2: serve ---------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA server configuration (history-API fallback, asset caching, healthz).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static bundle produced by the build stage.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
