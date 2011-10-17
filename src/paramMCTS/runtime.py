"""
runtime.py

This module provides all runtime components like master, worker and executor
classes.

classes:
    Master
    Worker
    Executor

"""

import threading
import multiprocessing
import queue
import time
import functools
import signal
import logging
import os
import math
import collections

import paramMCTS.types


Task = collections.namedtuple('Task', 'command, content')
Result = collections.namedtuple('Result', 'node, value')

TASK_STOP = 'stop'
TASK_PREFIX = 'prefix'
TASK_RUN = 'run'

LOG_LEVEL = logging.DEBUG


def get_logger(name, log_level=LOG_LEVEL):
    """Return configured logger"""
    log = logging.getLogger(name)
    log.setLevel(LOG_LEVEL)
    directory = os.path.join('log', time.strftime('%Y%m%d-%H%M%S'))
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    filename = os.path.join(directory, '{}.log'.format(name))
    fh = logging.FileHandler(filename)
    formatter = logging.Formatter('%(asctime)s - %(processName)s -'
            ' %(threadName)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    log.addHandler(fh)
    return log


class Master(object):
    """Master for MCTS execution and worker management."""

    def __init__(self, mpi, configuration, state_name, penalty=3,
            threads=True):
        self.__mpi = mpi
        self.__config = configuration
        self.__state_name = state_name
        self.__penalty = penalty
        queue_size = self.__mpi['size'] * 2
        if threads:
            self.__task_queue = queue.Queue(queue_size)
            self.__result_queue = queue.Queue()
            self._worker = WorkerThread
        else:
            self.__task_queue = multiprocessing.JoinableQueue(queue_size)
            self.__result_queue = multiprocessing.JoinableQueue()
            self._worker = WorkerProcess

        self.__destinations = range(1, self.__mpi['size'])
        self._stop = functools.partial(self.__mpi['comm'].send,
                Task(TASK_STOP, None))
        self.__terminate = threading.Event()
        self.__log = get_logger('master')
        self.__log.debug('master initialized')
        self.__worker = []
        self._create_workers()

    def _timer(self, seconds, pid, signal=signal.SIGTERM):
        """Send signal after seconds to pid."""
        self.__log.debug('start timer for %d seconds', seconds)
        time.sleep(seconds)
        self.__terminate.set()
        self.__log.debug('set termination event')

    def _create_workers(self):
        """Create worker (count: mpi_size - 1)."""
        mpi = self.__mpi
        for dest in self.__destinations:
            mpi['dest'] = dest
            worker = self._worker(mpi, self.__task_queue, self.__result_queue,
                    self.__config['instance_selector'])
            worker.daemon = True
            worker.start()
            self.__worker.append(worker)
            self.__log.debug('created worker for mpi rank %d', dest)

    def run(self, limit):
        """Run manager to add nodes to task queue and process results."""
        timer = threading.Thread(target=self._timer, kwargs={
                'seconds': limit*60, 'pid': os.getpid()})
        timer.daemon = True
        timer.start()
        task_upper_bound = self.__mpi['size']
        task_lower_bound = math.ceil(self.__mpi['size'] / 2)
        self.__log.debug('start master with task upper bound: %d task lower'
                ' bound %d', task_upper_bound, task_lower_bound)
        while not self.__terminate.is_set():
            leaf = self.__config['root'].select_leaf()
            self.__log.debug('leaf selected: %s', leaf.node)

            self.__task_queue.put(Task(TASK_RUN, leaf))
            if self.__task_queue.qsize() < task_upper_bound:
                continue
            while self.__task_queue.qsize() > task_lower_bound and \
                    not self.__terminate.is_set():
                try:
                    result = self.__result_queue.get(timeout=5)
                    try:
                        self._update(result)
                    finally:
                        self.__result_queue.task_done()
                except queue.Empty:
                    pass
            paramMCTS.configuration.save_state(self.__state_name, self.__config)
        # cleanup
        self.stop_all()
        paramMCTS.configuration.save_state(self.__state_name, self.__config)
        print(self.__config['root'].best_assignment())

    def _update(self, result):
        """Update MCTS tree with result."""
        leaf = frozenset(result.node.assignments)
        value = result.value if result.value is not None \
                else self.__penalty * self.__config['timeout']
        self.__log.debug('update nodes for result: %s / %f',
                result.node, value)
        amount = 0
        for node in paramMCTS.types.Node.get_nodes().values():
            params = frozenset(node.assignments)
            if params <= leaf:
                node.visits += 1
                node.value += value
                amount += 1
        self.__log.debug('%d nodes updated', amount)

    def stop(self, dest):
        """Send stop task to mpi dest."""
        self._stop(dest=dest, tag=dest)
        self.__log.debug('send stop message to executor %d', dest)

    def stop_all(self):
        """Send stop task to all worker."""
        for dest in self.__destinations:
            self.stop(dest)


class Worker(object):
    """Worker basic class which implements mpi communication."""

    def __init__(self, mpi, task_queue, result_queue, instance_selector):
        self.__task_queue = task_queue
        self.__result_queue = result_queue
        self.__instance_selector = instance_selector
        self.__log = get_logger('worker-{}'.format(mpi['dest']))
        self._send = functools.partial(mpi['comm'].send, dest=mpi['dest'],
                tag=mpi['dest'])
        self._recv = functools.partial(mpi['comm'].recv, source=mpi['dest'],
                tag=mpi['dest'])
        self.__log.debug('worker initizalized')

    def run(self):
        """Run worker and process tasks."""
        while True:
            try:
                task = self.__task_queue.get()
                assert task.command == TASK_RUN, 'send only run commands' \
                        ' by the worker'
                self._process(task)
            finally:
                self.__task_queue.task_done()

    def _process(self, task):
        """Send task to executor and process result."""
        task.content.assignment.append(
                self.__instance_selector.random_assignment())
        self.__log.debug('send task %s', task)

        self._send(task)
        result = self._recv()
        self.__log.debug('received result %s', result)
        self.__result_queue.put(result)

class WorkerThread(Worker, threading.Thread):
    """Worker threaded implementation."""

    def __init__(self, mpi, task_queue, result_queue, instance_selector):
        Worker.__init__(self, mpi, task_queue, result_queue, instance_selector)
        threading.Thread.__init__(self)


class WorkerProcess(Worker, multiprocessing.Process):
    """Worker multiprocessing implementation."""

    def __init__(self, mpi, task_queue, result_queue, instance_selector):
        Worker.__init__(self, mpi, task_queue, result_queue, instance_selector)
        multiprocessing.Process.__init__(self)


class Executor(object):
    """Executes algorithm for evaluation."""

    def __init__(self, mpi, program_caller, instance_variable):
        self.__program_caller = program_caller
        self.__log = get_logger('executor-{}'.format(mpi['rank']))
        self.__queue = queue.Queue()
        self._send = functools.partial(mpi['comm'].send, dest=0,
                tag=mpi['rank'])
        self._recv = functools.partial(mpi['comm'].recv, source=0,
                tag=mpi['rank'])
        self._call = functools.partial(program_caller.call,
                cat=instance_variable)
        signal.signal(signal.SIGTERM, self._handler)
        signal.signal(signal.SIGINT, self._handler)
        self.__log.debug('executor initialized')

    def listen(self):
        """Listen for mpi messages and process them."""
        receiver = threading.Thread(target=self._receive)
        receiver.daemon = True
        receiver.start()
        while True:
            task = self.__queue.get()
            try:
                if task.command == TASK_PREFIX:
                    self.__log.debug('received new prefix cmd: %s',
                            task.content)
                    self.__config['program_caller'].prefix_cmd = task.content
                    continue
                if task.command == TASK_RUN:
                    self.__log.debug('received run cmd for task: %s',
                            task.content)
                    self._process(task.content)
            finally:
                self.__queue.task_done()

    def _receive(self):
        """Listen for mpi messages and process them."""
        while True:
            task = self._recv()
            if task.command == TASK_STOP:
                self.__log.debug('received stop message')
                os.kill(os.getpid(), signal.SIGTERM)
                break
            else:
                self.__queue.put(task)

    def _process(self, leaf):
        """Process leaf node by executing parameter assignment."""
        result = self._call(leaf.assignment_dict())
        self.__log.debug('result for task: %s', result)
        if 'interrupted' in result['stdout']:
            self.__log.debug('send result as timeout to root')
            value = None
        else:
            value = float(result['stdout']['time'])
            self.__log.debug('send result (%f) to root',
                    float(result['stdout']['time']))
        self._send(Result(leaf.node, value))

    def _handler(self, signum, stack):
        """Catch signal and kill process and childs."""
        self.__program_caller.kill(signum)
        self.__log.debug('caught signal %d', signum)
        raise SystemExit()
