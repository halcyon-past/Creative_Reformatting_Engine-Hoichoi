# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/nginx-ssl.conf /etc/nginx/conf.d/nginx-ssl.conf
COPY frontend/entrypoint.sh /docker-entrypoint.d/40-ssl-check.sh
RUN chmod +x /docker-entrypoint.d/40-ssl-check.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443
