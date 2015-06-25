# Tugboat

Tugboat is [docker compose](https://docs.docker.com/compose/) under the hood with a new command line interface including native support for multiple .yml files and a friendlier syntax.

## Installation
`pip install tug`

## Usage

```
Describe your infrastructure with yaml files.

  Usage:
    tug2 ps
    tug2 COMMAND PROJECT [SERVICES ...]

  Common Commands:

    ps             List all running and available groups
    up             Update and run services
    diff           Describe the changes needed to update (not implemented yet)
    cull           Stop and delete services
    logs           Display group logs
    exec           Run a command inside a service (not implemented yet)

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
