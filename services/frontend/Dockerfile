FROM node:24.20.0-alpine3.24 AS build

WORKDIR /app
COPY services/frontend/package.json services/frontend/package-lock.json ./
RUN npm ci
COPY services/frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30.4-alpine3.24-slim

COPY services/frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=2s --retries=10 CMD wget -qO- http://127.0.0.1:8080/health || exit 1
