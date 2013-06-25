"""XBee 868 monitor's server module."""

from __future__ import unicode_literals

import errno
import json
import logging
import os
import socket
import struct

from pcore import str, bytes
from psys import eintr_retry

import xbee_868.stats

from xbee_868 import constants
from xbee_868.io_loop import FileObject

LOG = logging.getLogger(__name__)


class Server(FileObject):
    def __init__(self, io_loop):
        self.__client_id = 0

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.setblocking(False)

        try:
            try:
                os.unlink(constants.SERVER_SOCKET_PATH)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

            sock.bind(constants.SERVER_SOCKET_PATH)
            sock.listen(100)

            super(Server, self).__init__(io_loop, sock, "TODO")
        except:
            sock.close()
            raise


    def on_read(self):
        """Called when we have data to read."""

        try:
            connection = eintr_retry(self._file.accept)()
        except OSError as e:
            if e.errno != errno.ECONNABORTED:
                LOG.error("Unable to accept a connection: %s.", e)
                self.close()
        else:
            self.__client_id += 1
            LOG.debug("Accepting a new client connection #%s...", self.__client_id)
            _Client(self._weak_io_loop(), connection[0], self.__client_id)


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


class _Client(FileObject):
    def __init__(self, io_loop, sock, client_id):
        self.__client_id = client_id
        sock.setblocking(False)

        super(_Client, self).__init__(io_loop, sock, "TODO")

        LOG.debug("Sending sensor statistics to client #%s...", self.__client_id)
        stats = json.dumps(xbee_868.stats.get()).encode("utf-8")
        self._write(struct.pack(b"!Q", len(stats)) + stats)

        # TODO
        call = io_loop.call_after(1, self.__on_timed_out)
        self.add_on_close_handler(lambda: io_loop.cancel_call(call))


    def __on_timed_out(self):
        LOG.debug("Client #%s timed out.", self.__client_id)
        self.close()

    def on_hang_up(self):
        LOG.debug("Client #%s closed the connection.", self.__client_id)
        self.close()

    def on_write(self):
        """Called when we are able to write."""

        if self._write():
            LOG.debug("All statistics data has been successfully sent to client #%s.", self.__client_id)
            self.close()


    def poll_write(self):
        """Returns True if we need to poll the file for write availability."""

        return True
