#!/usr/bin/env python

import errno
import os
import logging
import select

import psys.poll
from psys import eintr_retry
from psys import bytes, str



import xbee_868.log
from xbee_868.io_loop import IOLoop
from xbee_868.sensor import Sensor

# TODO
LOG = logging.getLogger(__name__)


# TODO: handle connection lost

# fcntl.fcntl(self.fd, FCNTL.F_SETFL, os.O_NONBLOCK)

xbee_868.log.setup(debug_mode=True)
LOG.info("Staring the daemon...")

io_loop = IOLoop()
Sensor(io_loop)
io_loop.start()
#poll = psys.poll.Poll()
#poll.register(sensor.fileno(), poll.POLLIN)

#try:
#    while True:
#        for fd, epoll_flags in poll.poll():
#            sensor.on_read()
#finally:
#    poll.close()
