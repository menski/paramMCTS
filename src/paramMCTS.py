#!/usr/bin/env python3

import sys
import argparse
import socket
import time
import unittest

import mpi4py.MPI

import paramMCTS.configuration
import paramMCTS.types
import paramMCTS.runtime


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
    group.add_argument('-j', '--json', metavar='file', type=str,
            help='read hal json file')
    group.add_argument('-l', '--load', metavar='file', type=str,
            help='read saved dump')
    group.add_argument('-s', '--stats', metavar='file', type=str,
            help='print stats of save file')
    parser.add_argument('-d', '--dot', action='store_true', default=False,
            help='write MCTS graph as .dot file')
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
            default='bin/runsolver -W {timeout} -M {memory}',
            help='executable to call in front of the' \
            ' evaluation algorithm (default: %(default)s)')
    parser.add_argument('--threads', dest='threads', action='store_true',
            default=True, help='use worker threads (default)')
    parser.add_argument('--processes', dest='threads', action='store_false',
            help='use worker processes')
    parser.add_argument('--limit', metavar='minutes', type=int,
            default=60, help='time limit for paramMCTS execution')

    return parser.parse_args()


def test():
    """Test suite."""
    suite = unittest.TestLoader().discover(".")
    print(unittest.TextTestRunner().run(suite))


def stats(filename, dot=False):
    """Print stats and optional save .dot file."""
    config = paramMCTS.configuration.load_state(filename)
    print('Configuration')
    print('=============')
    for key in sorted(config.keys()):
        print('{:>20}: {}'.format(key, config[key]))
        print()
    print('{:>9}: {}'.format('Nodes', paramMCTS.types.Node.node_count()))
    print('{:>9}: {}'.format('Parameter',
            paramMCTS.types.Parameter.parameter_count()))
    print('{:>9}: {}'.format('best leaf', config['root'].best_assignment()))
    if dot:
        config['root'].to_dot(filename + '.dot')


def main(options):
    """Main routine for program."""

    state_name = 'paramMCTS-{}-{}.save'.format(time.strftime('%Y%m%d-%H%M%S'),
            socket.gethostname())

    mpi = dict()
    mpi['comm'] = mpi4py.MPI.COMM_WORLD
    mpi['rank'] = mpi['comm'].Get_rank()
    mpi['size'] = mpi['comm'].Get_size()

    if options.json is not None:
        config = paramMCTS.configuration.read_hal_json(options.json,
                options.instances, options.prefix.format(
                timeout=options.timeout, memory=options.memory))
        config['root'] = paramMCTS.types.Node()
        config['timeout'] = options.timeout
    elif options.load is not None:
        if mpi['rank'] == 0:
            config = paramMCTS.configuration.load_state(options.load,
                    master=True)
        else:
            config = paramMCTS.configuration.load_state(options.load,
                    master=False)

    if mpi['size'] == 1:
        print('ERROR: use mpirun -n N to start the program (N > 1)',
                file=sys.stderr)
        sys.exit(1)

    if mpi['rank'] == 0:
        # Master
        master = paramMCTS.runtime.Master(mpi, config, state_name,
                threads=options.threads)
        master.run(options.limit)
    else:
        # Executer
        executor = paramMCTS.runtime.Executor(mpi, config['program_caller'],
            config['instance_selector'].variable)
        executor.listen()


if __name__ == '__main__':
    opt = options()
    if opt.test:
        test()
    elif opt.stats:
        stats(opt.stats, opt.dot)
    else:
        main(opt)
