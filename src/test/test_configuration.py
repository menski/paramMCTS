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


class TestInstanceSelector(unittest.TestCase):
    """Test InstanceSelector creation and selection."""

    def setUp(self):
        paths = ['paramMCTS', 'test']
        self.abs_selector = paramMCTS.configuration.InstanceSelector(
                paths, abspath=True)
        self.rel_selector = paramMCTS.configuration.InstanceSelector(
                paths, abspath=False)
        self.automotive_selector = paramMCTS.configuration.InstanceSelector(
                ['instances/automotive'], abspath=False)

    def test_relativ_paths(self):
        selection = self.rel_selector.random()
        self.assertTrue(selection.startswith('paramMCTS') or
                selection.startswith('test'))

    def test_absolute_paths(self):
        selection = self.abs_selector.random()
        self.assertTrue(selection.startswith('/'))

    def test_count(self):
        self.assertEqual(len(self.automotive_selector.instances), 16)


class TestProgramCaller(unittest.TestCase):
    """Test ProgramCaller execution."""

    def setUp(self):
        self.callstring = paramMCTS.configuration.Callstring(
                '$instance$ --number $num$', {'num': 1})
        self.prefix_cmd = ' '.join(['bin/runsolver', '-M 300', '-W 30',
                '-w run.watcher'])
        self.instance_selector = paramMCTS.configuration.InstanceSelector(
                ['instances/automotive'], abspath=False)

    def test_executable(self):
        with self.assertRaises(paramMCTS.configuration.ExecutableError):
            paramMCTS.configuration.ProgramCaller('prg_not_exists')

        with self.assertRaises(paramMCTS.configuration.ExecutableError):
            paramMCTS.configuration.ProgramCaller('paramMCTS/configuration.py')

        paramMCTS.configuration.ProgramCaller('test/test_configuration.py')

    def test_regex(self):
        caller = paramMCTS.configuration.ProgramCaller('bin/clasp',
                regex={'stdout': 'Time    : $time$s'})
        self.assertEqual(caller.pattern['stdout'][0].pattern,
                r'Time    : (?P<time>\S+)s')
        self.assertCountEqual(caller.pattern['stderr'], [])

    def test_execution(self):
        caller = paramMCTS.configuration.ProgramCaller('bin/clasp',
                callstring=self.callstring, prefix_cmd=self.prefix_cmd,
                regex={'stdout': ['CPU Time    : $time$s',
                    'INTERRUPTED : $interrupted$']})
        result = caller.call({'instance': self.instance_selector.random()},
                cat='instance')
        self.assertCountEqual(result['stderr'], [])
        self.assertIn('time', result['stdout'])
        self.assertNotIn('interrupted', result['stdout'])

        self.prefix_cmd = ' '.join(['bin/runsolver', '-M 1', '-W 1',
                '-w run.watcher'])
        caller.prefix_cmd = self.prefix_cmd
        result = caller.call(
                {'instance': 'instances/automotive/0_0_1_2_0.0.bz2'},
                cat='instance')
        self.assertCountEqual(result['stderr'], [])
        self.assertIn('time', result['stdout'])
        self.assertIn('interrupted', result['stdout'])
        self.assertEqual(result['stdout']['interrupted'], '1')


if __name__ == '__main__':
    unittest.main()
