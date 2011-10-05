#!/usr/bin/env python3

import sys
import os
import random

sys.path.insert(1, os.path.join(sys.path[0], '..'))

import unittest

from paramMCTS import types


class TestNode(unittest.TestCase):
    """Test Node creation and child generation."""

    def setUp(self):
        types.add_parameter('a', (1, 2), None)
        types.add_parameter('b', ('a', 'b'), {'a': (1, 2)})
        types.add_parameter('c', (True, False), {'a': [2], 'b': ['a']})

    def tearDown(self):
        types.clear()

    def test_node_creation(self):
        l = len(types.NODE_DICT)
        self.assertEqual(l, 0)

        n = types.Node()
        l = len(types.NODE_DICT)
        self.assertEqual(l, 1)

        n1 = types.Node([1, 2])
        l = len(types.NODE_DICT)
        self.assertEqual(l, 2)

        n2 = types.Node((1, 2))
        l = len(types.NODE_DICT)
        self.assertEqual(l, 2)
        self.assertEqual(n1, n2)
        self.assertIs(n1, n2)

    def test_child_creation(self):
        l = len(types.NODE_DICT)
        self.assertEqual(l, 0)

        root = types.Node()
        child = root.generate_childs()
        l = len(types.NODE_DICT)
        self.assertEqual(l, 3)
        self.assertEqual(child[0][types.PARAM_NAME], 'a')

        rand_child = child.random_child()
        l = len(types.NODE_DICT)
        self.assertEqual(l, 3)
        self.assertEqual(rand_child[1][types.PARAM_NAME], 'b')

        child = rand_child.generate_childs()
        l = len(types.NODE_DICT)
        if rand_child[0][types.PARAM_VALUES] == 2 and \
                rand_child[1][types.PARAM_VALUES] == 'a':
            self.assertEqual(l, 5)
            self.assertEqual(child[2][types.PARAM_NAME], 'c')
        else:
            self.assertEqual(l, 3)
            self.assertEqual(child, rand_child)
            self.assertIs(child, rand_child)

    def test_select_leaf(self):
        root = types.Node()
        leaf = root.select_leaf()
        self.assertEqual(leaf[types.LEAF_NODE][0][types.PARAM_NAME], "a")
        self.assertGreater(len(leaf[types.LEAF_PATH]), 1)

        leaf2 = root.select_leaf()
        self.assertEqual(leaf2[types.LEAF_NODE][0][types.PARAM_NAME], "a")
        self.assertNotEqual(leaf, leaf2)

    def test_dot(self):
        root = types.Node()
        for i in range(10):
            leaf = root.select_leaf()
            leaf[types.LEAF_NODE].update(random.randint(1,10))
        root.to_dot(filename="test.dot")
        os.system("dot -Teps test.dot -o test.eps")


if __name__ == '__main__':
    unittest.main()
