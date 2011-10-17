"""
configuration.py

This module provides classes for callstrings, progammcaller and instance
chooser.

functions:
    open_file
    convert_regex
    read_hal_json

classes:
    Callstring
    ProgramCaller
    InstanceSelector

exceptions:
    ArgumentError
    VariableError
    InstanceError
    ExecutableError

"""


import re
import os
import random
import gzip
import bz2
import tempfile
import shlex
import subprocess
import json
import pickle

import paramMCTS.types


ARGUMENT_PATTERN = re.compile(
        r'(?P<b1>\[)?(-[-\w]+[ =])?(\$[-\$,\[\]\w]+)(?(b1)\])')
VARIABLE_PATTERN = re.compile(r'(\[)?,?\$([-\w]+)\$(?(1)\])')

ARG_OPT = 0
ARG_NAME = 1
ARG_VARS = 2
VAR_OPT = 0
VAR_NAME = 1

GZIP_MAGIC = b"\x1F\x8B"
BZIP_MAGIC = b"\x42\x5A"


def open_file(filename):
    """Return context manager for uncompressed, gzip or bzip file."""
    with open(filename, 'rb') as fin:
        magic = fin.read(len(GZIP_MAGIC))
    open_dict = {GZIP_MAGIC: gzip.open, BZIP_MAGIC: bz2.BZ2File}
    return open_dict.get(magic, open)(filename, 'rb')


def convert_regex(regex):
    """Return compiled regex with conversition of $test$ to (?P<test>\S+)."""
    if isinstance(regex, str):
        regex = [regex]
    return tuple([re.compile(re.sub(
            r'\$(?P<var>\S+)\$', r'(?P<\g<var>>\S+)', r)) for r in regex])


def read_hal_json(filename, instances, prefix_cmd):
    """Return dictonary with important elements from hal output file."""
    with open(filename, 'r') as fin:
        config = json.load(fin)[0]

    result = dict()

    # Read configuration space
    # 1. parse conditionals
    # 2. add parameters
    space = config['configurationSpace']
    conditionals = {parameter: {depends: frozenset(items['items']) for
            depends, items in definition[0].items()} for parameter, definition
            in space['conditionals'].items()}

    for parameter, definition in space["parameters"].items():
        paramMCTS.types.Parameter(parameter, definition["items"],
                conditionals.get(parameter, None))

    # Read scenario space
    # 1. parse constants
    space = config['scenarioSpace']['parameters']
    constants = dict()
    constants['num'] = space['num']['default']
    constants['seed'] = space['seed']['default']

    # Read implementation
    # 1. read instance file variable name
    # 2. create InstanceSelector
    # 3. create Callstring
    # 4. create ProgramCaller
    space = config['implementation']
    instance_variable = space['instanceSpace']['semantics'][
            'INSTANCE_FILE']
    result['instance_selector'] = InstanceSelector(instances,
            instance_variable)
    callstring = Callstring(space['inputFormat']['callstring'][0],
            constants)
    output_regex = space['outputFormat']
    output_regex['stdout'].append('INTERRUPTED : $interrupted$')
    result['program_caller'] = ProgramCaller(space['executable'], callstring,
            prefix_cmd, regex=output_regex)

    return result


def save_state(filename, configuration, compress=True):
    """Save state to file with optional compression."""
    try:
        if not os.path.isdir('save'):
            os.mkdir('save')
        filename = os.path.join('save', filename)
        state = (configuration, paramMCTS.types.Parameter.get_parameters(),
                paramMCTS.types.Node.get_nodes())
        open_func = gzip.open if compress else open
        with open_func(filename, 'wb') as fout:
            pickle.dump(state, fout, pickle.HIGHEST_PROTOCOL)
    except (EnvironmentError, pickle.PicklingError) as err:
        raise SaveError(str(err))


def load_state(filename, master=True):
    """Load state from file with optional reduced information."""
    try:
        with open_file(filename) as fin:
            configuration, parameters, nodes = pickle.load(fin)
            if master:
                paramMCTS.types.Parameter.set_parameters(parameters)
                paramMCTS.types.Node.set_nodes(nodes)
            else:
                paramMCTS.types.clear()
                del configuration['root']
            return configuration
    except (EnvironmentError, pickle.UnpicklingError) as err:
        raise LoadError(str(err))


class SaveError(Exception):
    """Exception raised during pickling state."""
    pass


class LoadError(Exception):
    """Exception raised during unpickling saved state."""
    pass


class ArgumentError(Exception):
    """Exception raised during argument assignment for a callstring."""
    pass


class VariableError(Exception):
    """Exception raised during variable assignment for a callstring."""
    pass


class InstanceError(Exception):
    """Exception raised during instance detection."""
    pass


class ExecutableError(Exception):
    """Exception raised if executable is not found or is not executable."""
    pass


class Callstring(object):
    """Parse a callstring and assign variable to it.

    Callstring(callstring, constants=None):
        callstring  : string to parse
        constants   : dictonary of constant values

    assign(assignment)
        return a assigned callstring
    """

    def __init__(self, callstring, constants=None):
        self.__callstring = None
        self.__constants = constants if constants is not None else dict()
        self._parse(callstring)

    @property
    def callstring(self):
        """Return value of callstring property."""
        return self.__callstring

    @property
    def constants(self):
        """Return value of constants property."""
        return self.__constants

    def _parse(self, callstring):
        """Set __callstring to nested tuple represantation."""
        self.__callstring = tuple([(bool(arg[ARG_OPT]), arg[ARG_NAME],
            tuple([(bool(var[VAR_OPT]), var[VAR_NAME])
                for var in VARIABLE_PATTERN.findall(arg[ARG_VARS])]))
            for arg in ARGUMENT_PATTERN.findall(callstring)])

    def assign(self, assignment):
        """Return an assignet callstring.

        Throws ArgumentError or VariableError if necessary variables are
        not represented in assignment dictonary.

        - assignment    : dictonary of assignments

        """
        return ' '.join([elem for elem in [self._format(arg, assignment)
            for arg in self.__callstring] if elem])

    def _format(self, arg, assignment):
        """Return assigned string for an argument."""
        try:
            variables = ','.join([vstr for vstr in
                [self._format_var(var, assignment) for var in arg[ARG_VARS]]
                if vstr])
        except VariableError as err:
            if not arg[ARG_OPT]:
                raise err
            else:
                return ""
        if not variables:
            if not arg[ARG_OPT]:
                raise ArgumentError(
                        'Argument not optional ("0")'.format(arg[ARG_NAME]))
            else:
                return ""
        return '{0}{1}'.format(arg[ARG_NAME], variables)

    def _format_var(self, var, assignment):
        """Return assigned value as a string for a variable."""
        name = var[VAR_NAME]
        if name in self.__constants:
            return str(self.__constants[name])
        elif name in assignment:
            return str(assignment[name])
        elif not var[VAR_OPT]:
            raise VariableError('Variable not optional "{0}"'.format(name))
        else:
            return ''

    def __str__(self):
        return str(self.callstring)


class ProgramCaller(object):
    """Save a program path and executes it with given arguments.

    ProgramCaller(path, callstring=None, prefix_cmd=None, regex=None)
        path        : path to executable
        callstring  : callstring instance for execution
        prefix_cmd  : command to prefix executable
        regex       : regex dictonary to match stdout and stderr

    call(assignment, cat=None)
        return dictonary of matched stdout and stderr
    """

    def __init__(self, path, callstring=None, prefix_cmd=None, regex=None):
        self.__path = path
        self.__callstring = callstring
        self.__prefix_cmd = prefix_cmd
        self.__pattern = {'stdout': [], 'stderr': []}
        self.__process = None
        self.__childs = None
        if regex is not None:
            for pipe in ('stdout', 'stderr'):
                if pipe in regex:
                    self.__pattern[pipe] = convert_regex(regex[pipe])
        self._test_executable()

    @property
    def path(self):
        """Return value of path property."""
        return self.__path

    @property
    def callstring(self):
        """Return value of callstring property."""
        return self.__callstring

    @callstring.setter
    def callstring(self, value):
        """Set value of callstring property."""
        self.__callstring = value

    @property
    def prefix_cmd(self):
        """Return value of prefix_cmd property."""
        return self.__prefix_cmd

    @prefix_cmd.setter
    def prefix_cmd(self, value):
        """Set value of prefix_cmd property."""
        self.__prefix_cmd = value

    @property
    def process(self):
        """Return value of process property."""
        return self.__process

    @property
    def childs(self):
        """Return value of childs property."""
        return self.__childs

    @property
    def pattern(self):
        """Return value of pattern property."""
        return self.__pattern

    def _test_executable(self):
        """Test if path exists, is a file and is executable.

        If not a ExecutableError exception is raised.

        """
        if not os.path.exists(self.__path):
            raise ExecutableError('Unable to find executable "{0}"'.format(
                self.__path))
        if not os.path.isfile(self.__path):
            raise ExecutableError('Path "{0}" is not a file'.format(
                self.__path))
        if not os.access(self.__path, os.X_OK):
            raise ExecutableError('File "{0}" is not executable'.format(
                self.__path))

    def _get_process_childs(self, ppid):
        """Return list of process childs pid."""
        try:
            return [int(pid) for pid in subprocess.check_output(shlex.split(
                'ps -o pid= --ppid {}'.format(ppid))).decode('utf8').split()]
        except subprocess.CalledProcessError:
            return None

    def call(self, assignment, cat=None):
        """Return regex matches from stdout and stderr of called program.

        Calls the program, prefixed with prefix_cmd if given and cat files
        to tempfiles if needed (e.g. compress files). After the execution
        the stdout_regex and stderr_regex lists are matched agains the
        stdout and stderr of the program. The result is a dict with the
        keys "stdout" and "stderr".

        - assignment    : assignment for callstring
        - cat           : attribut name of assignment to cat into a tempfile

        """
        assert self.callstring is not None, 'callstring has to be given'
        if cat is not None:
            with open_file(assignment[cat]) as fin, \
                    tempfile.NamedTemporaryFile(mode='wb', prefix='paramMCTS_',
                    delete=False) as fout:
                fout.write(fin.read())
                assignment[cat] = fout.name
        callstring = ' '.join([cstr for cstr in
            [self.prefix_cmd, self.path, self.callstring.assign(assignment)]
            if cstr is not None])
        args = shlex.split(callstring)

        with subprocess.Popen(args, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE) as self.__process:
            self.__childs = self._get_process_childs(self.process.pid)
            (stdout, stderr) = self.process.communicate()
        self.__process = None
        self.__childs = None

        if cat is not None:
            os.remove(assignment[cat])
        result = {'stdout': {}, 'stderr': {}}
        for regex in self.pattern['stdout']:
            match = regex.search(stdout.decode('utf8'))
            if match:
                result['stdout'].update(match.groupdict())
        for regex in self.pattern['stderr']:
            match = regex.search(stderr.decode('utf8'))
            if match:
                result['stderr'].update(match.groupdict())
        return result

    def kill(self, signum):
        """Terminate process and kill childs by signum."""
        if self.childs is not None:
            for child in self.childs:
                os.kill(child, signum)
        if self.process is not None:
            self.process.terminate()

    def __str__(self):
        return '({} ; {} ; {} | {})'.format(self.prefix_cmd, self.path,
                self.callstring, {name: [va.pattern for va in value] 
                    for name, value in self.pattern.items()})


class InstanceSelector(object):
    """Choose a instance from a set of paths.

    InstanceSelector(paths, variable, abspath=False)
        paths       : list of paths to instances directories
        variable    : variable name in callstring
        abspath     : toogle absolute paths

    random()
        returns a random selected instance path
    """

    def __init__(self, paths, variable, abspath=False):
        self.__instances = None
        self.__variable = variable
        self.__abspath = abspath
        self._find_instances(paths)

    @property
    def instances(self):
        """Return value of instances property."""
        return self.__instances

    @property
    def variable(self):
        """Return value of variable property."""
        return self.__variable

    def _find_instances(self, paths):
        """Set instances to a tuple of instance paths."""
        def raise_instance_error(err):
            """Raise InstanceError on error during os.walk."""
            raise InstanceError('Invalid instance path given "{0}"'.format(
                    err.filename))

        instances = list()
        pathfunc = lambda p: os.path.abspath(p) if self.__abspath else p
        for path in paths:
            for dirpath, _, filenames in os.walk(path,
                    onerror=raise_instance_error, followlinks=True):
                instances += [pathfunc(os.path.join(dirpath, filename))
                        for filename in filenames]
        self.__instances = tuple(instances)

    def random(self):
        """Return a random instances from instances tuple.

        Return None if instances tuple is empty.
        """
        if self.instances is not None and self.instances:
            return random.choice(self.instances)
        return None

    def random_assignment(self):
        """Return a random instance variable assignment."""
        instance = self.random()
        if instance is None:
            return None
        return paramMCTS.types.Assignment(self.__variable, instance)

    def __str__(self):
        return '({}: {})'.format(self.variable, self.instances)
