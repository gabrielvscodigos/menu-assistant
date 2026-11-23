# Front-end image: build the React app, then serve the static files with nginx, which
# also forwards /api to the API container (see nginx.conf). Built by compose.yaml.

# --- build stage -----------------------------------------------------------------------
FROM node:22-alpine AS build

# pnpm version pinned to match package.json "packageManager".
RUN npm install --global pnpm@10.34.9

WORKDIR /app

# Dependencies first, so source changes reuse the installed packages.
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# --- runtime stage: static files behind nginx --------------------------------------------
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1/"]
