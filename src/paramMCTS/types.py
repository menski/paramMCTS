"""
types.py

This module provides classes and functions for ndoes and parameters.

functions:
    clear

classes:
    Parameter
    Node
"""

import math
import random
import sys

LEAF_NODE = 0
LEAF_ASSIGNMENT = 1

UCT_C = math.sqrt(2)

EPSILON = sys.float_info.epsilon

GRAPH_TEMPLATE = 'digraph "paramMCTS" {{\nnode [shape=box];\n{0}\n}}'


def clear():
    """Clear all internal storages."""
    Parameter.clear_storage()
    Node.clear_storage()


class Parameter(object):
    """A parameter is defined by a name, a tuple of possible values and
    an optional condition dictonary.

    """

    __slots__ = ['__name', '__values', '__condition']

    __storage = {}

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

    def __str__(self):
        """Return string representation."""
        return '({0.name}={0.values}|cond: {0.condition})'.format(self)

    @classmethod
    def clear_storage(cls):
        """Clear internal parameter storage."""
        cls.__storage.clear()

    @classmethod
    def get_parameters(cls):
        """Return all internal stored parameters."""
        return cls.__storage.values()


class Assignment(object):
    """Assignment of a parameter."""

    __slots__ = ['__name', '__value']

    def __init__(self, name, value):
        self.__name = name
        self.__value = value

    @property
    def name(self):
        """Return value of name property."""
        return self.__name

    @property
    def value(self):
        """Return value of value property."""
        return self.__value

    def __str__(self):
        """Return string representation."""
        return '({0.name}={0.value})'.format(self)

    def __eq__(self, other):
        if isinstance(other, Assignment):
            return self.name == other.name and self.value == other.value
        elif isinstance(other, tuple) or isinstance(other, list):
            if len(other) == 2:
                return self.name == other[0] and self.value == other[1]
        else:
            return NotImplemented

    def __hash__(self):
        return hash((self.name, self.value))


class Node(object):
    """Save a ordered list of parameters, a set of childs, a value and visits.

    Node(assignment=None, save=True)
        assginment  : ordert list or tuple of assignments
        save        : save node in interal storage

    select_leaf(self):
        return a leaf node for evaluation

    update(self, value):
        update all nodes in path with value (also increase visits)
    """

    __slots__ = ['__assignments', '__childs', '__value', '__visits']

    __storage = {}

    def __new__(cls, assignments=None, save=True):
        if assignments is None:
            assignments = tuple()
        node = Node.__storage.get(frozenset(assignments), None)
        if node is None:
            node = object.__new__(cls)
            node.__assignments = tuple(assignments)
            node.__childs = None
            node.__value = 0
            node.__visits = 0
            if save:
                Node.__storage[frozenset(assignments)] = node
        return node

    @property
    def assignments(self):
        """Return value of assignments property."""
        return self.__assignments

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
    def visits(self, visits):
        """Set value of visits property."""
        self.__visits = visits

    @classmethod
    def clear_storage(cls):
        """Clear internal node storage."""
        cls.__storage.clear()

    @classmethod
    def get_nodes(cls):
        """Return all internal stored nodes."""
        return cls.__storage

    @classmethod
    def node_count(cls):
        """Return number of stored nodes."""
        return len(cls.__storage)

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
        if parameter.condition is None:
            return True
        for cname, cvalues in parameter.condition.items():
            for cvalue in cvalues:
                if (cname, cvalue) in self.assignments:
                    break
            else:
                return False
        return True

    def free_parameters(self):
        """Return a list of free parameters."""
        assigned_parameters = {assignment.name for assignment
                in self.assignments}
        return [param for param in Parameter.get_parameters()
                if param.name not in assigned_parameters
                and self.parameter_satisfied(param)]

    def generate_childs(self):
        """Returns a random child after all childs are created.

        Return self if no childs exists.

        """
        assert self.childs is None, 'Call generate childs only one time'

        free_parameters = self.free_parameters()
        childs = []
        for parameter in free_parameters:
            childs += [self.child(Assignment(parameter.name, value))
                    for value in parameter.values]
        if childs:
            self.__childs = frozenset(childs)
            return random.choice(childs)
        else:
            return self

    def child(self, assignment, save=True):
        """Return child node for a new assigned assignment."""
        return Node(list(self.assignments) + [assignment], save)

    def random_child(self):
        """Return a random child without creating a new Node."""
        free_parameters = self.free_parameters()
        if not free_parameters:
            return None
        new_parameter = random.choice(free_parameters)
        new_value = random.choice(new_parameter.values)
        return self.child(Assignment(new_parameter.name, new_value), False)

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

    def __getitem__(self, index):
        """Return assignment at index position."""
        return self.__assignments[index]

    def __iter__(self):
        """Return iterator over assignments."""
        return iter(self.__assignments)

    def __len__(self):
        """Return number of assignments."""
        return len(self.__assignments)

    def __str__(self):
        """Return string representation."""
        return str(self.__assignments)

