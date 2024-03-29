#!/usr/bin/env python3

import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], '..'))

import unittest

from paramMCTS import configuration, types


class TestInstanceSelector(unittest.TestCase):
    """Test InstanceSelector creation and selection."""

    def setUp(self):
        paths = ['paramMCTS', 'test']
        self.abs_selector = configuration.InstanceSelector(
                paths, 'instance', abspath=True)
        self.rel_selector = configuration.InstanceSelector(
                paths, 'instance', abspath=False)
        self.automotive_selector = configuration.InstanceSelector(
                ['instances/automotive'], 'instance', abspath=False)

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
        self.callstring = configuration.Callstring(
                '$instance$ --number $num$', {'num': 1})
        self.prefix_cmd = ' '.join(['bin/runsolver', '-M 300', '-W 30',
                '-w run.watcher'])
        self.instance_selector = configuration.InstanceSelector(
                ['instances/automotive'], 'instance', abspath=False)

    def test_executable(self):
        with self.assertRaises(configuration.ExecutableError):
            configuration.ProgramCaller('prg_not_exists')

        with self.assertRaises(configuration.ExecutableError):
            configuration.ProgramCaller('paramMCTS/configuration.py')

        configuration.ProgramCaller('test/test_configuration.py')

    def test_regex(self):
        caller = configuration.ProgramCaller('bin/clasp',
                regex={'stdout': 'Time    : $time$s'})
        self.assertEqual(caller.pattern['stdout'][0].pattern,
                r'Time    : (?P<time>\S+)s')
        self.assertCountEqual(caller.pattern['stderr'], [])

    def test_execution(self):
        caller = configuration.ProgramCaller('bin/clasp',
                callstring=self.callstring, prefix_cmd=self.prefix_cmd,
                regex={'stdout': ['CPU Time    : $time$s',
                    'INTERRUPTED : $interrupted$']})
        result = caller.call({self.instance_selector.variable:
                self.instance_selector.random()},
                cat=self.instance_selector.variable)
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


class TestJsonInput(unittest.TestCase):
    """Test json input parsing."""

    def setUp(self):
        self.json_file = 'etc/hal-clasp.json'

    def tearDown(self):
        types.clear()

    def test_read(self):
        cfg = configuration.read_hal_json(self.json_file, ['instances/'], None)
        self.assertEqual(types.Parameter.parameter_count(), 34)

        p = types.Parameter('backprop')
        self.assertEqual(p.name, 'backprop')
        self.assertTupleEqual(p.values, tuple(["yes", "no"]))
        self.assertIsNone(p.condition)

        p = types.Parameter('recursive-str')
        self.assertTupleEqual(p.values, tuple(["yes", "no"]))
        self.assertIsNotNone(p.condition)
        self.assertDictEqual(p.condition, {'strengthen':
                frozenset(["bin", "tern", "yes"])})

        self.assertEqual(cfg['instance_selector'].variable, 'instanceFile')

        caller = cfg['program_caller']
        self.assertEqual(caller.path, 'bin/clasp')
        self.assertEqual(caller.pattern['stdout'][0].pattern,
                r'CPU Time    : (?P<time>\S+)s')
        callstring = caller.callstring
        self.assertDictEqual(callstring.constants, {'num': 1, 'seed': 1})


class TestStatePickle(unittest.TestCase):
    """Test state pickling."""

    def setUp(self):
        self.filename = 'test.sav'
        types.Parameter('a', (1, 2), None)
        types.Parameter('b', (2, 3), None)
        root = types.Node()
        root.generate_childs()
        root.value += 100
        root.visits += 1
        config = dict()
        config['root'] = root
        config['instance_selector'] = configuration.InstanceSelector(
                ['instances/'], 'instance')
        config['program_caller'] = configuration.ProgramCaller('bin/clasp',
                configuration.Callstring('$instance$'))
        self.config = config

    def test_pickling(self):
        parameter_count = types.Parameter.parameter_count()
        node_count = types.Node.node_count()
        instances_count = len(self.config['instance_selector'].instances)
        instance_variable = self.config['instance_selector'].variable
        program_path = self.config['program_caller'].path
        root = self.config['root']
        root_value = self.config['root'].value
        root_visits = self.config['root'].visits

        configuration.save_state(self.filename, self.config)
        types.clear()
        self.assertEqual(types.Parameter.parameter_count(), 0)
        self.assertEqual(types.Node.node_count(), 0)

        config = configuration.load_state('save/' + self.filename)
        self.assertEqual(types.Parameter.parameter_count(), parameter_count)
        self.assertEqual(types.Node.node_count(), node_count)
        self.assertEqual(len(config['instance_selector'].instances),
                instances_count)
        self.assertEqual(config['instance_selector'].variable,
                instance_variable)
        self.assertEqual(config['program_caller'].path, program_path)
        self.assertTupleEqual(config['root'].assignments, root.assignments)
        self.assertGreater(len(config['root'].childs), 0)
        self.assertEqual(config['root'].value, root_value)
        self.assertEqual(config['root'].visits, root_visits)

        self.filename += '.gz'
        configuration.save_state(self.filename, config, compress=True)
        types.clear()
        config = configuration.load_state('save/' + self.filename,
                master=False)
        self.assertEqual(types.Parameter.parameter_count(), 0)
        self.assertEqual(types.Node.node_count(), 0)
        self.assertTrue('instance_selector' in config)
        self.assertEqual(config['program_caller'].path, program_path)
        self.assertFalse('root' in config)
        self.assertEqual(len(config), 2)



if __name__ == '__main__':
    unittest.main()
