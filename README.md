# Tugboat
Tugboat is [docker compose](https://docs.docker.com/compose/) under the hood with a new command line interface including native support for multiple .yml files and a friendlier syntax.

## Installation
`pip install tug`

Set a `TUGBOAT_PATH` environment variable to all your directories of `.yaml` files and the `tug` command will work from anywhere.

## Usage

```
Describe your infrastructure with yaml files.

Usage:
    tug ps
    tug ls
    tug exec PROJECT SERVICE [COMMANDS ...]
    tug COMMAND PROJECT [SERVICES ...]

Common Commands:

    ps             List all running projects
    ls             List all running and available projects
    up             Update and run services
    diff           Describe the changes needed to update
    cull           Stop and delete services
    logs           Display container logs
    exec           Run a command inside a container

Management Commands:

    kill           Gracefully terminate services
    down           Stop services
    rm             Delete services
    recreate       Stop, delete, then run services
    build          Build services
    rebuild        Build services from scratch

Options:

    -h --help      Display this usage information
    -v --version   Display the version number

```

The yml format is identical to the [docker compose yml format](https://docs.docker.com/compose/yml/).

## Example

```
> cd examples
> pwd
/Users/tcoats/Open/tugboat-py/examples
> export TUGBOAT_PATH=/Users/tcoats/Open/tugboat-py/examples:./
> tug ps

  couchdb                 1 Up

> tug down couchdb
Killing couchdb_d_1 ... done
Stopping couchdb_d_1 ... done

  couchdb services:

  d_1                     Exit 137    (host)

> tug ps

  couchdb                 1 Exit 137

> tug ls

  couchdb                 1 Exit 137
  redis                   1 Uncreated

> tug up redis

  redis services:

  d_1                     Up          172.17.0.2

> cat redis.yml
d:
  image: redis
  ports:
  - "6379:6379"
> cat redis.yml
d:
  image: redis
  ports:
  - "6379:6379"
  - "80:80"
> tug diff redis

  redis convergence plan:

  d                       recreate    redis_d_1

> tug up redis

  redis services:

  d_1                     Up          172.17.0.2

> tug diff redis

  redis convergence plan:

  d                       noop        redis_d_1

> tug logs couchdb
d_1 | Apache CouchDB 1.6.1 (LogLevel=info) is starting.
d_1 | Apache CouchDB has started. Time to relax.
d_1 | [info] [<0.32.0>] Apache CouchDB has started on http://0.0.0.0:5984/
...streaming
```

