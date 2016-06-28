from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


import signal
import os
import subprocess
import yaml
import contextlib
import json
import logging
import re
import sys
from os import path
from inspect import getdoc
from operator import attrgetter
from docopt import docopt, DocoptExit

logging.basicConfig()

from docker.errors import APIError
from requests.exceptions import ReadTimeout

from compose.cli import signals
from compose.config import config, ConfigurationError, parse_environment
from compose.config.serialize import serialize_config
from compose.const import API_VERSION_TO_ENGINE_VERSION, DEFAULT_TIMEOUT, HTTP_TIMEOUT, IS_WINDOWS_PLATFORM
from compose.progress_stream import StreamOutputError
from compose.project import Project
from compose.project import NoSuchService
from compose.service import BuildError, ConvergenceStrategy, ImageType, NeedsBuildError
from compose.cli.command import get_config_path_from_options, project_from_options
from compose.cli.docopt_command import DocoptCommand, NoSuchCommand
from compose.cli.errors import UserError
from compose.cli.formatter import ConsoleWarningFormatter, Formatter
from compose.cli.log_printer import LogPrinter
from compose.cli.utils import get_version_info, yesno
from .client import docker_client
from .__init__ import __version__


if not IS_WINDOWS_PLATFORM:
    from dockerpty.pty import PseudoTerminal, RunOperation

def main():
    try:
        Usage()
    except (KeyboardInterrupt, signals.ShutdownException):
        print("Aborting.")
        sys.exit(1)
    except (UserError, NoSuchService, ConfigurationError) as e:
        print(e.msg)
        sys.exit(1)
    except NoSuchCommand as e:
        commands = "\n".join(parse_doc_section("commands:", getdoc(e.supercommand)))
        print("No such command: %s\n\n%s", e.command, commands)
        sys.exit(1)
    except APIError as e:
        log_api_error(e)
        sys.exit(1)
    except BuildError as e:
        print("Service '%s' failed to build: %s" % (e.service.name, e.reason))
        sys.exit(1)
    except StreamOutputError as e:
        print(e)
        sys.exit(1)
    except ReadTimeout as e:
        print("An HTTP request took too long to complete.")
        sys.exit(1)

def log_api_error(e):
    if 'client is newer than server' in e.explanation:
        # we need JSON formatted errors. In the meantime...
        # TODO: fix this by refactoring project dispatch
        # http://github.com/docker/compose/pull/2832#commitcomment-15923800
        client_version = e.explanation.split('client API version: ')[1].split(',')[0]
        print(
            "The engine version is lesser than the minimum required by "
            "compose. Your current project requires a Docker Engine of "
            "version {version} or superior.".format(
                version=API_VERSION_TO_ENGINE_VERSION[client_version]
            ))
    else:
        print(e.explanation)

yaml_re = re.compile('\.yaml$|\.yml$')

class Usage(object):


    """Describe your infrastructure with yaml files.

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

    """

    def __init__(self):
        docstring = getdoc(Usage)
        options = None
        try:
            options = docopt(docstring,
                argv=sys.argv[1:],
                version=__version__,
                options_first=True)
        except DocoptExit:
            raise SystemExit(docstring)

        if 'ps' in options and options['ps']:
            self._ps()
            return

        if 'ls' in options and options['ls']:
            self._ls()
            return

        projectname = self._clean_project_name(options['PROJECT'])

        if 'exec' in options and options['exec']:
          self._exec(projectname, options['SERVICE'], options['COMMANDS'])
          return

        # 'command' references a function on this class
        command = options['COMMAND']
        if not hasattr(self, command):
            print('{command} command not found'.format(command=command))
            sys.exit(1)

        servicenames = options['SERVICES']

        config_data = self._get_config(projectname)

        client = docker_client()

        project = Project.from_config(
            projectname,
            config_data,
            client)

        handle = getattr(self, command)
        handle(project, projectname, servicenames)

    def _clean_project_name(self, name):
        return yaml_re.sub('', name)

    def _load(self, filename):
        working_dir = path.dirname(filename)
        loaded = config.load_yaml(filename)
        return config.load(config.find(working_dir, [path.basename(filename)]))

    def _get_config(self, name):
        config_files = self._get_available_projects()
        for config_file in config_files:
            projectname = self._clean_project_name(path.basename(config_file))
            if name == projectname:
                return self._load(config_file)
        raise ConfigurationError("Project filename '%s' not found in the current directory" % name)

    def _get_available_projects(self):
        search_directories = set()
        tugboat_path = os.environ.get('TUGBOAT_PATH') or './'
        for directory in tugboat_path.split(':'):
            search_directories.add(os.path.abspath(directory))

        projects = []
        for directory in search_directories:
            for filename in os.listdir(directory):
                if yaml_re.search(filename):
                    projects.append(path.join(directory, filename))
        return projects

    def _ps(self):
        client = docker_client()
        config_files = self._get_available_projects()
        containers = client.containers(all=True)
        unknown = {}
        for container in containers:
            unknown[container['Id']] = client.inspect_container(
                container['Id'])
        if len(config_files) != 0:
            print('')
        for config_file in config_files:
            projectname = self._clean_project_name(path.basename(config_file))
            try:
                config_data = self._get_config(projectname)
            except (ConfigurationError) as e:
                continue
            project = Project.from_config(
                projectname,
                config_data,
                client)
            services = project.get_services()

            counts = {}

            for service in services:
                c = service.containers(stopped=True) + service.containers(one_off=True)
                if len(c) == 0:
                    if not 'Uncreated' in counts:
                        counts['Uncreated'] = 0
                    counts['Uncreated'] += 1
                for container in c:
                    del unknown[container.id]
                    if not container.human_readable_state in counts:
                        counts[container.human_readable_state] = 0
                    counts[container.human_readable_state] += 1

            humancounts = []
            for state in counts:
                humancounts.append('{count} {state}'.format(
                    count=counts[state],
                    state=state))
            if len(counts) == 1 and 'Uncreated' in counts:
                continue;
            print('  {name: <24}{counts}'.format(
                name=projectname,
                counts=','.join(humancounts)))

        print()

    def _ls(self):
        client = docker_client()
        config_files = self._get_available_projects()
        containers = client.containers(all=True)
        unknown = {}
        ignoredyaml = 0
        for container in containers:
            unknown[container['Id']] = client.inspect_container(
                container['Id'])
        if len(config_files) != 0:
            print()
        for config_file in config_files:
            projectname = self._clean_project_name(path.basename(config_file))
            try:
                config_data = self._get_config(projectname)
            except (ConfigurationError) as e:
                print('  {name: <24}Configuration error'.format(name=projectname))
                ignoredyaml += 1
                continue
            project = Project.from_config(
                projectname,
                config_data,
                client)
            services = project.get_services()

            counts = {}

            for service in services:
                c = service.containers(stopped=True) + service.containers(one_off=True)
                if len(c) == 0:
                    if not 'Uncreated' in counts:
                        counts['Uncreated'] = 0
                    counts['Uncreated'] += 1
                for container in c:
                    del unknown[container.id]
                    if not container.human_readable_state in counts:
                        counts[container.human_readable_state] = 0
                    counts[container.human_readable_state] += 1

            humancounts = []
            for state in counts:
                humancounts.append('{count} {state}'.format(
                    count=counts[state],
                    state=state))
            print('  {name: <24}{counts}'.format(
                name=projectname,
                counts=','.join(humancounts)))

        if len(unknown) != 0:
            print()
            print('  Containers not tracked by compose/tugboat:')
            print()
        for key in unknown:
            detail = unknown[key]
            name = detail['Name']
            if name.startswith('/'):
                name = name[1:]
            ip = detail['NetworkSettings']['IPAddress']
            if ip == '':
                ip = '(host)'
            print('  {name: <24}{state: <12}{ip: <17}'.format(
                name=name,
                state='',
                ip=ip))
        print()

        if ignoredyaml > 0:
            plural = 's'
            if ignoredyaml is 1:
                plural = ''
            print('  {count} file{plural} failed to parse'.format(
                count=ignoredyaml,
                plural=plural))
            print()

    def ps(self, project, projectname, servicenames):
        print()
        print('  {name} services:'.format(name=projectname))
        print()
        services = project.get_services(service_names=servicenames)
        for service in services:
            containers = service.containers(stopped=True) + service.containers(one_off=True)
            if len(containers) == 0:
                print('  {name: <24}{state: <12}{ip: <17}'.format(
                    name=service.name,
                    state='Uncreated',
                    ip=''))
            for container in containers:
                name = container.name_without_project
                ip = container.get('NetworkSettings.IPAddress')
                if ip == '':
                    ip = '(host)'
                state = container.human_readable_state
                print('  {name: <24}{state: <12}{ip: <17}'.format(
                    name=name,
                    state=state,
                    ip=ip))
        print()

    def ls(self, project, projectname, servicenames):
        self.ps(project, projectname, servicenames)

    def build(self, project, projectname, servicenames):
        project.build(service_names=servicenames, no_cache=False)

    def rebuild(self, project, projectname, servicenames):
        project.build(service_names=servicenames, no_cache=True)

    def kill(self, project, projectname, servicenames):
        project.kill(service_names=servicenames, signal='SIGTERM')
        self.ps(project, projectname, servicenames)

    def logs(self, project, projectname, servicenames):
        containers = project.containers(
            service_names=servicenames,
            stopped=True)
        print('Attaching to', ', '.join(c.name for c in containers))
        LogPrinter(containers).run() #, log_args={'follow': True, 'tail': 100}).run()

    def pull(self, project, projectname, servicenames):
        project.pull(service_names=servicenames)

    def rm(self, project, projectname, servicenames):
        project.remove_stopped(service_names=servicenames)
        self.ps(project, projectname, servicenames)

    def down(self, project, projectname, servicenames):
        project.kill(service_names=servicenames, signal='SIGTERM')
        try:
            project.stop(service_names=servicenames)
        except:
            pass
        self.ps(project, projectname, servicenames)

    def cull(self, project, projectname, servicenames):
        project.kill(service_names=servicenames, signal='SIGTERM')
        try:
            project.stop(service_names=servicenames)
        except:
            pass
        project.remove_stopped(service_names=servicenames)
        self.ps(project, projectname, servicenames)

    def recreate(self, project, projectname, servicenames):
        project.kill(service_names=servicenames, signal='SIGTERM')
        try:
            project.stop(service_names=servicenames)
        except:
            pass
        project.remove_stopped(service_names=servicenames)
        self.up(project, projectname, servicenames)

    def up(self, project, projectname, servicenames):
        containers = project.containers(stopped=True) + project.containers(one_off=True)
        unknown = {}
        for container in containers:
            unknown[container.id] = container
        services = project.get_services(servicenames, include_deps=True)
        plans = project._get_convergence_plans(services, ConvergenceStrategy.changed)
        for service in plans:
            plan = plans[service]
            for container in plan.containers:
                del unknown[container.id]
        project.up(service_names=servicenames)

        if len(servicenames) == 0:
            for id in unknown:
                container = unknown[id]
                if container.is_running:
                    container.kill(signal='SIGTERM')
                    try:
                        container.client.wait(container.id, timeout=10)
                    except ReadTimeout as e:
                        pass
                    container.stop()
                    try:
                        container.client.wait(container.id, timeout=10)
                    except ReadTimeout as e:
                        pass
                container.remove()

        self.ps(project, projectname, servicenames)

    def diff(self, project, projectname, servicenames):
        containers = project.containers(stopped=True) + project.containers(one_off=True)
        unknown = {}
        for container in containers:
            unknown[container.id] = container
        services = project.get_services(servicenames, include_deps=True)
        plans = project._get_convergence_plans(services, ConvergenceStrategy.changed)

        print()
        print('  {name} convergence plan:'.format(name=projectname))
        print()
        for service in plans:
            plan = plans[service]
            service_containers = []
            for container in plan.containers:
                del unknown[container.id]
                service_containers.append(container.name)
            print('  {name: <24}{action: <12}{containers}'.format(
                name=service,
                action=plan.action,
                containers=', '.join(service_containers)))
        # TODO: Add this in when up starts deleting unknown containers.
        for id in unknown:
            container = unknown[id]
            print('  {name: <24}{action: <12}'.format(
                name=container.name,
                action='delete'))
        print()

    # TODO: look in the yaml file?
    def _exec(self, projectname, servicename, commands):
        containername = '{projectname}_{servicename}_1'.format(
            projectname=projectname,
            servicename=servicename)
        command = commands
        if command is None or not command:
            command = ['/bin/bash']
        print()
        print('  docker exec -it {containername} {command}'.format(
            containername=containername,
            command=' '.join(command)))
        print()
        command = ['docker', 'exec', '-it', containername] + command
        sys.exit(subprocess.call(command))
