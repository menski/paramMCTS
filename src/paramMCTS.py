#!/usr/bin/env python3

import argparse
import unittest

import paramMCTS.configuration


VERSION = 0.1
DESCRIPTION = ('paramMCTS is an auto-configuration tool, that uses the'
        ' techniques of the Monte Carlo Tree Search algorithm.')


def options():
    """Return options settings readed from commandline."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('--version', action='version', version='%(prog)s'
            ' {0}'.format(VERSION))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--test', action='store_true', help='run test suite')
    group.add_argument('-j', '--json', metavar='file',
            help='read hal json file')
    group.add_argument('-l', '--load', metavar='file', help='read saved dump')
    parser.add_argument('-i', '--instances', metavar='path',
            help='paths to instances directories (default: %(default)s)',
            default=['instances/'], type=str, nargs='+')
    parser.add_argument('-m', '--memory', metavar='limit', type=int,
            default=2000, help='memory limit for evaluation algorithm'
            ' execution in MB (default: %(default)s)')
    parser.add_argument('-t', '--timeout', metavar='seconds', type=int,
            default=600, help='timeout for evaluation algorithm execution'
            ' in seconds (default: %(default)s)')
    parser.add_argument('-p', '--prefix', metavar='cmd', type=str,
            default='bin/runsolver -W {timeout} -M {memory}' \
            ' -w runsolver.watcher', help='executable to call in front of the' \
            ' evaluation algorithm (default: %(default)s)')

    return parser.parse_args()


def test():
    """Test suite."""
    suite = unittest.TestLoader().discover(".")
    print(unittest.TextTestRunner().run(suite))


def main(options):
    """Main routine for program."""
    if options.json is not None:
        config = paramMCTS.configuration.read_hal_json(options.json)
        config['instance_selector'] = paramMCTS.configuration.InstanceSelector(
                options.instances, config['instance_variable'])
        caller = config['program_caller']
        caller.prefix_cmd = options.prefix.format(timeout=options.timeout,
                memory=options.memory)
        config['prefix_cmd'] = options.prefix
    elif options.load is not None:
        pass


if __name__ == '__main__':
    opt = options()
    if opt.test:
        test()
    else:
        main(opt)
