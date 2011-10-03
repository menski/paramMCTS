#!/usr/bin/env python3

"""
configuration.py

This module provides classes for callstrings, worker configurations,
master configurations and instance chooser.

classes:
    Callstring

exceptions:
    ArgumentError
    VariableError

"""


import re


ARGUMENT_PATTERN = re.compile(
        r'(?P<b1>\[)?(-[-\w]+[ =])?(\$[-\$,\[\]\w]+)(?(b1)\])')
VARIABLE_PATTERN = re.compile(r'(\[)?,?\$([-\w]+)\$(?(1)\])')

ARG_OPT = 0
ARG_NAME = 1
ARG_VARS = 2
VAR_OPT = 0
VAR_NAME = 1


class ArgumentError(Exception):
    """Exception throw during argument assignment for a callstring."""
    pass


class VariableError(Exception):
    """Exception throw during variable assignment for a callstring."""
    pass


class Callstring(object):
    """Parse a callstring and assign variable to it.

    Callstring(callstring, constants=None):
        callstring  : string to parse
        constants   : dictonary of constant values
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
