# Multi-stage build for the Vue 3 frontend (PRD §10, task 6.4).
# Stage 1 compiles the static bundle; stage 2 serves it with nginx.

# ---- Stage 1: build the static bundle -------------------------------------
# Node 22 matches the LTS used in development.
FROM node:22 AS build

WORKDIR /app

# Install dependencies from the lockfile first for layer caching.
COPY package.json package-lock.json ./
RUN npm ci

# Copy the sources (node_modules, dist and .env are excluded by .dockerignore;
# the API base URL and limits come from build args, never from a local .env).
COPY . .

# Build-time configuration (api.ts reads these via import.meta.env and fails
# with `config_missing` when VITE_API_BASE_URL is empty). Defaults mirror the
# backend values; docker-compose.yml overrides the base URL to the published
# backend port. MAX_* values must stay equal to the backend .env.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_MAX_DOCUMENTS_PER_QUERY=10
ARG VITE_MAX_QUESTION_CHARS=2000
ARG VITE_POLL_INTERVAL_MS=2000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_MAX_DOCUMENTS_PER_QUERY=${VITE_MAX_DOCUMENTS_PER_QUERY} \
    VITE_MAX_QUESTION_CHARS=${VITE_MAX_QUESTION_CHARS} \
    VITE_POLL_INTERVAL_MS=${VITE_POLL_INTERVAL_MS}

RUN npm run build

# ---- Stage 2: serve the static bundle --------------------------------------
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
