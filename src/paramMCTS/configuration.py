#!/usr/bin/env python3

"""
configuration.py

This module provides classes for callstrings, worker configurations,
master configurations and instance chooser.

functions:
    open_file
    convert_regex

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
                stderr=subprocess.PIPE) as proc:
            (stdout, stderr) = proc.communicate()

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


class InstanceSelector(object):
    """Choose a instance from a set of paths.

    InstanceSelector(paths, abspath=True)
        paths       : list of paths to instances directories
        abspath     : toogle absolute paths

    random()
        returns a random selected instance path
    """

    def __init__(self, paths, abspath=True):
        self.__instances = None
        self.__abspath = abspath
        self._find_instances(paths)

    @property
    def instances(self):
        """Return value of instances property."""
        return self.__instances

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
