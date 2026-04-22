# Multi-stage build: Vite build, then serve static assets via Caddy.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2-alpine
WORKDIR /srv
COPY --from=build /app/dist /srv
RUN printf ':8080 {\n\troot * /srv\n\ttry_files {path} /index.html\n\tfile_server\n}\n' > /etc/caddy/Caddyfile
EXPOSE 8080
