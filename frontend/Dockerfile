# --- Builder stage ---
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json* bun.lock* ./
RUN npm ci

COPY . .

# Build-time API URL (overridable)
ARG VITE_GRAPHQL_URL=http://localhost:8000/graphql
ENV VITE_GRAPHQL_URL=$VITE_GRAPHQL_URL

# Demo mode OFF by default in prod builds (fabricated consultants never shown live)
ARG VITE_ENABLE_DEMO_MODE=false
ENV VITE_ENABLE_DEMO_MODE=$VITE_ENABLE_DEMO_MODE

RUN npm run build

# --- Production stage ---
FROM nginx:stable-alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html

# SPA routing + security headers.
# The CSP connect-src must include the GraphQL backend origin, which is a
# different origin from the one nginx serves the SPA on.
ARG VITE_GRAPHQL_URL=http://localhost:8000/graphql
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template
RUN API_ORIGIN=$(printf '%s' "$VITE_GRAPHQL_URL" | sed -E 's#^(https?://[^/]+).*#\1#') \
    && sed "s#__API_ORIGIN__#${API_ORIGIN}#" /etc/nginx/conf.d/default.conf.template \
       > /etc/nginx/conf.d/default.conf \
    && rm /etc/nginx/conf.d/default.conf.template \
    && nginx -t

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
