# ── Frontend Dockerfile ───────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app
ARG REACT_APP_API_BASE_URL=/api
ARG REACT_APP_WS_BASE_URL=
ENV REACT_APP_API_BASE_URL=${REACT_APP_API_BASE_URL}
ENV REACT_APP_WS_BASE_URL=${REACT_APP_WS_BASE_URL}
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# ── Serve with nginx ──────────────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
