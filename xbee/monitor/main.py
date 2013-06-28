"""The monitor's main module."""

from __future__ import unicode_literals

import argparse
import errno
import fcntl
import logging
import os
import signal
import sys

from psys import eintr_retry

import xbee.common.log
import xbee.common.io_loop
from xbee import common

import xbee.monitor.config
import xbee.monitor.sensor
import xbee.monitor.server
import xbee.monitor.stats
from xbee import monitor

xbee # Suppress PyFlakes warnings

LOG = logging.getLogger("xbee.monitor.main" if __name__ == "__main__" else __name__)


class _MainLoop(common.io_loop.IoLoop):
    """The monitor's main loop."""

    def __init__(self):
        super(_MainLoop, self).__init__()

        try:
            monitor.server.Server(self)
            self.__deferred_call = self.call_next(self.__connect_to_sensors)
            monitor.stats.monitor_started()
        except:
            self.close()
            raise


    def stop(self):
        """Stops the I/O loop."""

        self.cancel_call(self.__deferred_call)
        super(_MainLoop, self).stop()


    def __connect_to_sensors(self):
        """Connects to XBee devices."""

        try:
            monitor.sensor.connect(self)
        finally:
            self.__deferred_call = self.call_after(10, self.__connect_to_sensors)



class _TerminationSignal(common.io_loop.FileObject):
    """UNIX termination signal monitor."""

    def __init__(self, io_loop, fd):
        super(_TerminationSignal, self).__init__(
            io_loop, os.fdopen(fd, "rb"), "Termination signal monitor")


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


    def on_read(self):
        """Called when we have data to read."""

        LOG.info("Got a termination signal. Exiting...")
        self._weak_io_loop().stop()
        self.close()



def main():
    """The daemon's main function."""

    parser = argparse.ArgumentParser(description="XBee monitor")
    parser.add_argument("-d", "--debug", action="store_true",
        help="print debug messages")

    args = parser.parse_args()

    try:
        monitor.config.load()
        common.log.setup("xbee-monitor", debug_mode=args.debug)
    except Exception as e:
        sys.exit("Unable to start the daemon: {0}".format(e))

    LOG.info("Starting the daemon...")

    try:
        with _MainLoop() as io_loop:
            signals = (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT)
            read_fd, write_fd = os.pipe()

            try:
                try:
                    _configure_termination_signals(
                        io_loop, signals, read_fd, write_fd)
                except:
                    eintr_retry(os.close)(read_fd)
                    raise

                io_loop.start()
            finally:
                for sig in signals:
                    signal.signal(sig, signal.SIG_IGN)

                eintr_retry(os.close)(write_fd)
    except Exception as e:
        LOG.error("The daemon has crashed: %s", e)


def _configure_termination_signals(io_loop, signals, read_fd, write_fd):
    """Configures UNIX termination signal handling."""

    fcntl.fcntl(read_fd, fcntl.F_SETFL, os.O_NONBLOCK)
    fcntl.fcntl(write_fd, fcntl.F_SETFL, os.O_NONBLOCK)

    def on_terminate(signum, stack):
        try:
            eintr_retry(os.write)(write_fd, b"\0")
        except EnvironmentError as e:
            if e.errno not in (errno.EPIPE, errno.EWOULDBLOCK):
                LOG.error("Failed to send termination signal to I/O loop: %s.", e)

    for sig in signals:
        signal.signal(sig, on_terminate)

    _TerminationSignal(io_loop, read_fd)



if __name__ == "__main__":
    main()
