#!/usr/bin/env python

import errno
import logging
import os
import select
import socket
import struct
import time

import psys.poll
from psys import eintr_retry
from psys import bytes, str

from xbee_868 import constants
from xbee_868.core import Error, LogicalError



import xbee_868.log
import xbee_868.sensor
from xbee_868.server import Server
from xbee_868.io_loop import IoLoop


# TODO
LOG = logging.getLogger(__name__)


# TODO: handle connection lost

# fcntl.fcntl(self.fd, FCNTL.F_SETFL, os.O_NONBLOCK)



class MainLoop(IoLoop):
    def __init__(self):
        super(MainLoop, self).__init__()
        self.__sensors = {}
        Server(self)
        #self.call_next(self.__connect_to_sensors)



    def __connect_to_sensors(self):
        try:
            pass
            #xbee_868.sensor.connect(self)
        finally:
            self.call_after(5, self.__connect_to_sensors)


def main():
    xbee_868.log.setup(debug_mode=False)
    LOG.info("Staring the daemon...")

    io_loop = MainLoop()
    io_loop.start()
    io_loop.close()


if __name__ == "__main__":
    main()
