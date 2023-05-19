import os
import json
import errno
import fcntl
import logging
import tempfile as tf
from dwiqc.state import State
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseTask(ABC):
    def __init__(self, outdir, tempdir=None, pipenv=None):
        self._outdir = outdir
        self._tempdir = tempdir
        self._pipenv = pipenv
        self._tempdir = tempdir if tempdir else tf.gettempdir()
        self._logdir = os.path.join(outdir, 'logs')
        self._prov = os.path.join(self._logdir, 'provenance.json')
        self.build()

    @staticmethod
    def state(prov):
        if os.path.exists(prov):
            # attempt to acquire a lock on provenance file
            fd = os.open(prov, os.O_RDWR|os.O_CREAT)
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                logger.debug('successfully locked %s', prov)
            except IOError as e:
                if e.errno == errno.EWOULDBLOCK:
                    logger.debug('another process has already locked %s', prov)
                    return State.RUNNING
                raise e
            # check returncode
            with open(prov) as fo:
                js = json.load(fo)
            if js['returncode'] is None:
                return State.TERMINATED
            elif js['returncode'] == 0:
                return State.COMPLETE
            else:
                return State.FAILED
        return State.NOT_FOUND

    @abstractmethod
    def build(self):
        pass

    def workdir(self):
        if not os.path.exists(self._tempdir):
            os.makedirs(self._tempdir)
        return tf.mkdtemp(suffix='.dwiqc', dir=self._tempdir)

    def logdir(self):
        if not os.path.exists(self._logdir):
            os.makedirs(self._logdir)
        return self._logdir

    @property
    def command(self):
        return self.job.command
