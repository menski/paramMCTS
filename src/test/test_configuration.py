#!/usr/bin/env python3

import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], '..'))

import unittest

import paramMCTS.configuration


class TestCallstring(unittest.TestCase):
    """Test Callstring creation and assignment."""

    def setUp(self):
        self.callstring = paramMCTS.configuration.Callstring(
                '$ins-file$ --number $num$ --test=$a$,$b$[,$c$] [--opt=$d1$]',
                {'num': 1})

    def test_assignment(self):
        assignment = {'ins-file': 'instance.lp'}
        with self.assertRaises(paramMCTS.configuration.VariableError):
            self.callstring.assign(assignment)

        assignment['a'] = ''
        assignment['b'] = ''
        with self.assertRaises(paramMCTS.configuration.ArgumentError):
            self.callstring.assign(assignment)

        assignment['a'] = 'A'
        assignment['b'] = 'B'
        self.assertEqual(self.callstring.assign(assignment),
                'instance.lp --number 1 --test=A,B')

        assignment['d1'] = 'D1'
        self.assertEqual(self.callstring.assign(assignment),
                'instance.lp --number 1 --test=A,B --opt=D1')


if __name__ == '__main__':
    unittest.main()
