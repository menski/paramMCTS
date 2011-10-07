"""
types.py

This module provides classes and functions for ndoes and parameters.

functions:
    clear
    add_parameter
    get_parameter
    get_parameters
    get_nodes

classes:
    Node
"""

import math
import random
import sys

PARAM_NAME = 0
PARAM_VALUES = 1
PARAM_CONDITION = 2

LEAF_NODE = 0
LEAF_ASSIGNMENT = 1

PARAM_DICT = dict()
NODE_DICT = dict()

UCT_C = math.sqrt(2)

EPSILON = sys.float_info.epsilon

GRAPH_TEMPLATE = 'digraph "paramMCTS" {{\nnode [shape=box];\n{0}\n}}'


class Parameter(object):
    """A parameter is defined by a name, a tuple of possible values and
    an optional condition dictonary.

    """

    __storage = {}

    __slots__ = ['__name', '__values', '__condition']

    def __new__(cls, name, values, condition):
        param = Parameter.__storage.get(name, None)
        if param is None:
            param = object.__new__(cls)
            param.__name = name
            param.__values = values
            param.__condition = condition
            Parameter.__storage[name] = param
        return param

    @property
    def name(self):
        """Return value of name property."""
        return self.__name

    @property
    def values(self):
        """Return value of values property."""
        return self.__values

    @property
    def condition(self):
        """Return value of condition property."""
        return self.__condition


def clear():
    """Clear state and remove all nodes and parameters."""
    PARAM_DICT.clear()
    NODE_DICT.clear()


def add_parameter(name, values, condition=None):
    """Add parameter definition."""
    PARAM_DICT[name] = (name, tuple(values), condition)


def get_parameter(parameter):
    """Return parameter definition."""
    return PARAM_DICT[parameter]


def get_parameters():
    """Return all parameters."""
    return PARAM_DICT.values()


def get_nodes():
    """Return all nodes."""
    return NODE_DICT.values()


class Node(tuple):
    """Save a ordered list of parameters, a set of childs, a value and visits.

    Node(parameters=None, save=True)
        parameters  : ordert list or tuple of parameters
        save        : save node in NODE_DICT

    def select_leaf(self):
        return a leaf node for evaluation

    def update(self, value):
        update all nodes in path with value (also increase visits)
    """

    def __new__(cls, parameters=None, save=True):
        if parameters is None:
            parameters = tuple()
        node = NODE_DICT.get(frozenset(parameters), None)
        if node is None:
            node = tuple.__new__(cls, parameters)
            node.__childs = None
            node.__value = 0
            node.__visits = 0
            if save:
                NODE_DICT[frozenset(node)] = node
        return node

    @property
    def childs(self):
        """Return value of childs property."""
        return self.__childs

    @property
    def value(self):
        """Return value of value property."""
        return self.__value

    @value.setter
    def value(self, value):
        """Set value of value property."""
        self.__value = value

    @property
    def visits(self):
        """Return value of visits property."""
        return self.__visits

    @visits.setter
    def visits(self, value):
        """Set value of visits property."""
        self.__visits = value

    def select_leaf(self):
        """Return a leaf node for evaluation."""
        node = self
        while not node.is_leaf():
            node = node.select_child()
        child = node.generate_childs()
        return (child, child.random_leaf())

    def select_child(self):
        """Return best child node."""
        return max(self.childs, key=lambda x: x.uct(self))

    def update(self, value):
        """Update all nodes in path with value (also increase visits)."""
        node = self
        while True:
            node.value += value
            node.visits += 1
            if not node:
                break
            node = Node(node[:-1])

    def uct(self, parent):
        """Return UCT value for node."""
        visits = self.visits + EPSILON
        value = parent.value / (parent.visits + EPSILON) - (self.value / visits)
        rand = EPSILON * random.random()
        return value / visits + rand + \
                UCT_C * math.sqrt(math.log(parent.visits + 1) / visits)

    def parameter_satisfied(self, parameter):
        """Return True if a parameter can be assigned."""
        if parameter[PARAM_CONDITION] is None:
            return True
        for cname, cvalues in parameter[PARAM_CONDITION].items():
            for cvalue in cvalues:
                if (cname, cvalue) in self:
                    break
            else:
                return False
        return True

    def free_parameters(self):
        """Return a list of free parameters."""
        assigned_parameters = {param[PARAM_NAME] for param in self}
        return [param for param in get_parameters()
                if param[PARAM_NAME] not in assigned_parameters
                and self.parameter_satisfied(param)]

    def generate_childs(self):
        """Returns a random child after all childs are created.

        Return self if no childs exists.

        """
        assert self.childs is None, 'Call generate childs only one time'

        free_parameters = self.free_parameters()
        childs = []
        for parameter in free_parameters:
            childs += [self.child((parameter[PARAM_NAME], value))
                    for value in parameter[PARAM_VALUES]]
        if childs:
            self.__childs = frozenset(childs)
            return random.choice(childs)
        else:
            return self

    def child(self, parameter, save=True):
        """Return child node for a new assigned parameter."""
        return Node(list(self) + [parameter], save)

    def random_child(self):
        """Return a random child without creating a new Node."""
        free_parameters = self.free_parameters()
        if not free_parameters:
            return None
        new_parameter = random.choice(free_parameters)
        new_value = random.choice(new_parameter[PARAM_VALUES])
        return self.child((new_parameter[PARAM_NAME], new_value), False)

    def random_leaf(self):
        """Return random leaf without creating new Nodes."""
        node = self
        while True:
            last = node
            node = node.random_child()
            if node is None:
                return list(last)

    def is_leaf(self):
        """Return True if no childs exists."""
        return self.childs is None

    def to_dot(self, filename=None):
        """Create dot graph and returns it (optional save it to a file)."""
        graph = GRAPH_TEMPLATE.format(self.dot_string())
        if filename is not None:
            with open(filename, 'w') as fout:
                fout.write(graph)
        return graph

    def dot_string(self, parent=None):
        """Return string in dot language."""
        name = hash(self)
        label = '{0} [label="{1}\\nvalue:{1.value}' \
                '  visits:{1.visits}  uct:{2:.3f}"]'.format(name, self,
                        self.uct(parent) if parent is not None else 0.0)
        if self.is_leaf():
            return label

        childs = [child for child in self.childs if child.visits > 0]

        return '{0}\n{1} -> {{{2}}}\n{3}'.format(label, name,
                '; '.join([str(hash(child)) for child in childs]),
                '\n'.join([child.dot_string(self) for child in childs]))
