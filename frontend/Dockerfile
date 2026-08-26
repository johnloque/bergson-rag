# Multi-stage: build the static bundle with Node, then serve it from a
# minimal nginx image -- no Node toolchain or node_modules ships in the
# final image (Sprint 9, docs/ROADMAP.md).
FROM node:24-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# CRITICAL: Vite bakes env vars into the bundle at build time -- the
# browser has no access to docker-compose's runtime `environment:`, so the
# API base URL has to be a build ARG here, and it must be a URL the user's
# BROWSER can reach (the api service's host-mapped port, e.g.
# http://localhost:8000), never the internal Docker service name
# (http://api:8000) -- that name only resolves container-to-container.
# Get this wrong and the image still builds and can still pass a
# container-only smoke test, then fails silently for every real browser
# user. See docker-compose.yml's `frontend.build.args` and
# scripts/test_frontend_arg.sh, which specifically guards against this.
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
