[![Task Status](https://community-tc.services.mozilla.com/api/github/v1/repository/MozillaSecurity/WebCompatManager/master/badge.svg)](https://community-tc.services.mozilla.com/api/github/v1/repository/MozillaSecurity/WebCompatManager/master/latest)
[![codecov](https://codecov.io/gh/MozillaSecurity/WebCompatManager/branch/master/graph/badge.svg)](https://codecov.io/gh/MozillaSecurity/WebCompatManager)
[![Matrix](https://img.shields.io/badge/dynamic/json?color=green&label=chat&query=%24.chunk[%3F(%40.canonical_alias%3D%3D%22%23fuzzing%3Amozilla.org%22)].num_joined_members&suffix=%20users&url=https%3A%2F%2Fmozilla.modular.im%2F_matrix%2Fclient%2Fr0%2FpublicRooms&style=flat&logo=matrix)](https://riot.im/app/#/room/#fuzzing:mozilla.org)

# What is WebCompatManager

WebCompatManager is a dashboard for analysing Brokemn Site Reporter
reports and other web compatibility issues.

## Local Development

The server part of WebCompatManager is a Django application, with a vue frontend.

### Frontend

The frontend is built using webpack.

For local development:

```
$ cd server/frontend
$ npm install
$ npm run start
```

This will cause the frontend components to be rebuilt when anything changes.

### Server

You can set the server up just like any other Django project. The Django
configuration file is found at `server/server/settings.py`. The default will
work, but for a production setup, you should at least review the database
settings.

The server is expected to be run using [`uv`](https://docs.astral.sh/uv/)

To setup the server, run the following commands:

```
$ uv run -p 3.12 --extra=server server/manage.py migrate
```

Create the webcompatmanager user.
```
$ uv run -p 3.12 --extra=server server/manage.py createsuperuser
Username (leave blank to use 'user'): webcompatmanager
Email address: webcompatmanager@internal.com
Password:
Password (again):
Superuser created successfully.
```

It is now possible to run the development server locally:
```
$ uv run -p 3.12 --extra=server server/manage.py runserver
```

Log in using the credentials created above.

### Tests

Lints are run with pre-commit. This can be installed as a Git hook, or run manually using:

```
uv run --extra=dev -p 3.12 pre-commit run --all
```

Tests are run using tox:
```
uv run --extra=dev -p 3.12 tox
```

### Redis

For some commands e.g, importing data, a [Redis](https://redis.io/)
server is also required, and can be installed on a Debian-based Linux
with:

```sudo apt-get install redis-server```

### Importing some reports for testing

This requires first authenticating with gcloud.

```uv run -p 3.12 --extra=server server/manage.py import_reports_from_bigquery --since <date>```


### Important changes in settings.py
It is important that you edit WebCompatManager/server/settings.py and adjust the following variables according to your needs.

    ALLOWED_HOSTS = ['host']
    CSRF_TRUSTED_ORIGINS = ['scheme://host']

See [ALLOWED_HOSTS](https://docs.djangoproject.com/en/4.1/ref/settings/#allowed-hosts) and [CSRF_TRUSTED_ORIGINS](https://docs.djangoproject.com/en/4.1/ref/settings/#csrf-trusted-origins) documentation.


You may also want to increase the maximum size in bytes allowed in a request body. The default of 2.5MB may not be enough
in some cases by adding the following variable.

    DATA_UPLOAD_MAX_MEMORY_SIZE = <YOUR VALUE HERE>

See [DATA_UPLOAD_MAX_MEMORY_SIZE](https://docs.djangoproject.com/en/4.1/ref/settings/#data-upload-max-memory-size)

## Production

### Using Apache+WSGI for a production setup

To properly run WebCompatManager in a production setup, using Apache+WSGI is the
recommended way.

In the `examples/apache2/` directory you'll find an example vhost file that
shows you how to run WebCompatManager in an Apache+WSGI setup. You should
adjust the configuration to use HTTPs if you don't plan to use any sort of
TLS load balancer in front of it.

### Getting/Creating the authentication token for clients

Use the following command to get an authentication token for a Django user:

`python manage.py get_auth_token username`

You can use the user that you created during `syncdb` for simple setups.

### Server Cronjobs

The following is an example crontab using `cronic` to run several important
WebCompatManager jobs:

```
# Fetch the status of all bugs from our external bug tracker(s)
*/15 * * * * cd /path/to/WebCompatManager/server && cronic python manage.py bug_update_status
# Cleanup old report entries and signatures according to configuration
*/30 * * * * cd /path/to/WebCompatManager/server && cronic python manage.py cleanup_old_reports
# Attempt to fit recently added report entries into existing buckets
*/5  * * * * cd /path/to/WebCompatManager/server && cronic python manage.py triage_new_reports
# Export all signatures to a zip file for downloading by clients
*/30 * * * * cd /path/to/WebCompatManager/server && cronic python manage.py export_signatures files/signatures.new.zip mv files/signatures.new.zip files/signatures.zip
```

### Run server with Docker

A docker image is available by building the `Dockerfile`.

You can easily run a local server (and Mysql database server) by using [docker-composer](https://docs.docker.com/compose/):

```console
docker compose up
```

On a first run, you must execute the database migrations:

```console
docker compose exec backend python manage.py migrate
```

And create a superuser to be able to log in on http://localhost:8000

```console
docker compose exec backend python manage.py createsuperuser
```

By default, the docker image uses Django settings set in Python module `server.settings_docker`, with the following settings:
- `DEBUG = False` to enable production mode
- `ALLOWED_HOSTS = ["localhost", ]` to allow development usage on `http://localhost:8000`

You can customize settings by mounting a file from your host into the container:

```yaml
volumes:
  - "./settings_docker.py:/src/server/server/settings_docker.py:ro"
```

### Managing Permissions

To manage user permissions, first SSH into the production server and then:

* To list permissions for any user run: `sudo docker exec -it webcompatmanager python manage.py ls_permission [ldap email]`

* Grant write-access to the reports to a user run:
  `sudo docker exec -it webcompatmanager python manage.py add_permission [ldap email] reportmanager_write`
