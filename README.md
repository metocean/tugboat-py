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

