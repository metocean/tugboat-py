# Tugboat

Tugboat is [docker compose](https://docs.docker.com/compose/) under the hood with a new command line interface including native support for multiple .yml files and a friendlier syntax.

## Usage

```
Define and run multi-container applications with Docker.

  Usage:
    tug2 ps
    tug2 exec PROJECT SERVICE
    tug2 COMMAND PROJECT [SERVICES ...]

  Common Commands:

    ps             List all running and available groups
    up             Update and run services
    down           Stop services
    diff           Describe the changes needed to update

  Management Commands:

    rm             Delete services
    cull           Stop and delete services
    recreate       Stop, delete, then run services
    kill           Gracefully terminate services
    build          Build services
    rebuild        Build services from scratch
    logs           Display group logs
    exec           Run a command inside a service

  Options:

    -h --help      Display this usage information
    -v --version   Display the version number
```

The yml format is identical to the [docker compose yml format](https://docs.docker.com/compose/yml/).
