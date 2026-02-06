FROM node:18-alpine AS frontend

COPY server/frontend /src
RUN chown -R node:node /src
USER node
WORKDIR /src

RUN npm install
RUN npm run production

FROM ghcr.io/astral-sh/uv:python3.12-alpine AS backend

RUN apk add --no-cache build-base git mariadb-dev

RUN adduser -D worker && \
   apk add --no-cache bash git mariadb-client mariadb-connector-c openssh-client-default && \
   rm -rf /var/log/*

COPY . /src/
RUN cd /src && uv sync --locked --extra=server --extra=docker

# Retrieve previous Javascript build
COPY --from=frontend /src/dist/ /src/server/frontend/dist/

# Use a custom settings file that can be overwritten
ENV DJANGO_SETTINGS_MODULE="server.settings_docker"

WORKDIR /src/server

# Collect staticfiles, including Vue.js build
RUN uv run --extra=server  --extra=docker manage.py collectstatic --no-input

# Run with gunicorn, using container's port 80
ENV PORT=80
EXPOSE 80
CMD ["uv", "run", "--extra", "server", "--extra", "docker", "gunicorn", "--bind", "0.0.0.0:80", "--error-logfile", "-", "--access-logfile", "-", "--capture-output", "server.wsgi"]
