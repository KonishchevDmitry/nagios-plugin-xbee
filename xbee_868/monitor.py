"""The monitor's main module."""

import errno
import fcntl
import logging
import os
import signal
import sys

from psys import eintr_retry

import xbee_868.io_loop
import xbee_868.log
import xbee_868.sensor
import xbee_868.server

LOG = logging.getLogger("xbee_868.monitor" if __name__ == "__main__" else __name__)


class _MainLoop(xbee_868.io_loop.IoLoop):
    """The monitor's main loop."""

    def __init__(self):
        super(_MainLoop, self).__init__()

        try:
            xbee_868.server.Server(self)
            self.__deferred_call = self.call_next(self.__connect_to_sensors)
        except:
            self.close()
            raise


    def stop(self):
        """Stops the I/O loop."""

        self.cancel_call(self.__deferred_call)
        super(_MainLoop, self).stop()


    def __connect_to_sensors(self):
        """Connects to XBee 868 devices."""

        try:
            # TODO
            pass
#            xbee_868.sensor.connect(self)
        finally:
            self.__deferred_call = self.call_after(5, self.__connect_to_sensors)



class _TerminationSignal(xbee_868.io_loop.FileObject):
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

    xbee_868.log.setup(debug_mode="--debug" in sys.argv[1:])
    LOG.info("Starting the daemon...")

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


def _configure_termination_signals(io_loop, signals, read_fd, write_fd):
    """Configures UNIX termination signal handling."""

    fcntl.fcntl(read_fd, fcntl.F_SETFL, os.O_NONBLOCK)
    fcntl.fcntl(write_fd, fcntl.F_SETFL, os.O_NONBLOCK)

    def on_terminate(signum, stack):
        try:
            eintr_retry(os.write)(write_fd, b"\0")
        except OSError as e:
            if e.errno not in (errno.EPIPE, errno.EWOULDBLOCK):
                LOG.error("Failed to send termination signal to I/O loop: %s.", e.strerror)

    for sig in signals:
        signal.signal(sig, on_terminate)

    _TerminationSignal(io_loop, read_fd)



if __name__ == "__main__":
    main()
