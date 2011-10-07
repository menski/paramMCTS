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
        types.Parameter('a', (1, 2), None)
        types.Parameter('b', ('a', 'b'), {'a': (1, 2)})
        types.Parameter('c', (True, False), {'a': [2], 'b': ['a']})

    def tearDown(self):
        types.clear()

    def test_node_creation(self):
        self.assertEqual(types.Node.node_count(), 0)

        n = types.Node()
        self.assertEqual(types.Node.node_count(), 1)

        n1 = types.Node([1, 2])
        self.assertEqual(types.Node.node_count(), 2)

        n2 = types.Node((1, 2))
        self.assertEqual(types.Node.node_count(), 2)
        self.assertEqual(n1, n2)
        self.assertIs(n1, n2)

    def test_child_creation(self):
        self.assertEqual(types.Node.node_count(), 0)

        root = types.Node()
        child = root.generate_childs()
        self.assertEqual(types.Node.node_count(), 3)
        self.assertEqual(child[0].name, 'a')

        rand_child = child.random_child()
        self.assertEqual(types.Node.node_count(), 3)
        self.assertEqual(rand_child[1].name, 'b')

        child = rand_child.generate_childs()
        l = types.Node.node_count()
        if rand_child[0].value == 2 and rand_child[1].value == 'a':
            self.assertEqual(l, 5)
            self.assertEqual(child[2].name, 'c')
        else:
            self.assertEqual(l, 3)
            self.assertEqual(child, rand_child)
            self.assertIs(child, rand_child)

    def test_select_leaf(self):
        root = types.Node()
        leaf = root.select_leaf()
        self.assertEqual(leaf.node[0].name, "a")
        self.assertGreater(len(leaf.assignment), 1)

        leaf2 = root.select_leaf()
        self.assertEqual(leaf2.node[0].name, "a")
        self.assertNotEqual(leaf, leaf2)

    def test_dot(self):
        root = types.Node()
        for i in range(10):
            leaf = root.select_leaf()
            leaf.node.update(random.randint(1,10))
        root.to_dot(filename="test.dot")
        os.system("dot -Teps test.dot -o test.eps")


if __name__ == '__main__':
    unittest.main()
