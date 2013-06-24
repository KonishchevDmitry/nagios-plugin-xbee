#!/usr/bin/env python

import errno
import logging
import os
import select
import time

import psys.poll
from psys import eintr_retry
from psys import bytes, str

from xbee_868.core import Error, LogicalError



import xbee_868.log
import xbee_868.sensor
from xbee_868.io_loop import IOLoop


# TODO
LOG = logging.getLogger(__name__)


# TODO: handle connection lost

# fcntl.fcntl(self.fd, FCNTL.F_SETFL, os.O_NONBLOCK)


class MainLoop(IOLoop):
    def __init__(self):
        super(MainLoop, self).__init__()
        self.__sensors = {}
        self.call(self.__connect_to_sensors)


    def __connect_to_sensors(self):
        try:
            xbee_868.sensor.connect(self)
        finally:
            self.call_after(5, self.__connect_to_sensors)


xbee_868.log.setup(debug_mode=True)
LOG.info("Staring the daemon...")

io_loop = MainLoop()
#connect(io_loop)
io_loop.start(precision=-1)
#poll = psys.poll.Poll()
#poll.register(sensor.fileno(), poll.POLLIN)

#try:
#    while True:
#        for fd, epoll_flags in poll.poll():
#            sensor.on_read()
#finally:
#    poll.close()
