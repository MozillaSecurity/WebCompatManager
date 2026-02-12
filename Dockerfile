FROM node:18-alpine AS frontend

COPY server/frontend /src
RUN chown -R node:node /src
USER node
WORKDIR /src

RUN npm install
RUN npm run production

FROM ubuntu:25.10 AS backend

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       bash \
       build-essential \
       git \
       libmariadb-dev \
       mariadb-client \
       openssh-client \
       pkg-config && \
    rm -rf /var/lib/apt/lists/* /var/log/*

RUN adduser --disabled-password worker

COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /uvx /bin/

COPY . /src/
RUN cd /src && uv sync --locked --extra=server --extra=docker

# Retrieve previous Javascript build
COPY --from=frontend /src/dist/ /src/server/frontend/dist/

RUN chown -R worker:worker /src
USER worker

# Use a custom settings file that can be overwritten
ENV DJANGO_SETTINGS_MODULE="server.settings_docker"

WORKDIR /src/server

# Collect staticfiles, including Vue.js build
RUN uv run --extra=server  --extra=docker manage.py collectstatic --no-input

# Run with gunicorn, using container's port 80
ENV PORT=80
EXPOSE 80
CMD ["uv", "run", "--extra", "server", "--extra", "docker", "gunicorn", "--bind", "0.0.0.0:80", "--error-logfile", "-", "--access-logfile", "-", "--capture-output", "server.wsgi"]
