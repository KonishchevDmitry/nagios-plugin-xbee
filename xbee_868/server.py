"""XBee 868 monitor's server module."""

from __future__ import unicode_literals

import errno
import json
import logging
import os
import socket
import struct

from psys import eintr_retry

import xbee_868.stats

from xbee_868 import constants
from xbee_868.core import Error
from xbee_868.io_loop import FileObject

LOG = logging.getLogger(__name__)


class Server(FileObject):
    """The monitor server socket."""

    def __init__(self, io_loop):
        self.__client_id = 0

        path = constants.SERVER_SOCKET_PATH
        LOG.info("Listening to client connections at '%s'...", path)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            try:
                os.unlink(path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise Error("Unable to delete '{0}': {1}.", path, e.strerror)

            sock.setblocking(False)

            try:
                sock.bind(path)
                sock.listen(128)
            except OSError as e:
                raise Error("Unable to create a UNIX socket '{0}': {1}.", path, e.strerror)

            super(Server, self).__init__(io_loop, sock, "Monitor's server socket")
        except:
            eintr_retry(sock.close())
            raise


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


    def on_read(self):
        """Called when we have data to read."""

        try:
            connection = eintr_retry(self._file.accept)()[0]
        except OSError as e:
            if e.errno != errno.ECONNABORTED:
                LOG.error("Unable to accept a connection: %s.", e.strerror)
        else:
            connection_name = "Client connection #{0}".format(self.__client_id)
            self.__client_id += 1

            LOG.debug("Accepting a new %s...", connection_name)

            try:
                _Client(self._weak_io_loop(), connection, connection_name)
            except Exception as e:
                LOG.error("Failed to accept %s: %s.", connection_name, e)
                eintr_retry(connection.close())


    def stop(self):
        """Called when the I/O loop ends its work."""

        self.close()



class _Client(FileObject):
    """A client connection socket."""

    def __init__(self, io_loop, sock, name):
        sock.setblocking(False)
        super(_Client, self).__init__(io_loop, sock, name)

        try:
            LOG.info("Sending sensor statistics to %s...", self)

            stats = json.dumps(xbee_868.stats.get()).encode("utf-8")
            message = struct.pack(b"!Q", len(stats)) + stats

            if self._write(message):
                self.close()
            else:
                self.add_deferred_call(
                    io_loop.call_after(constants.IPC_TIMEOUT, self.__on_timed_out))
        except Exception:
            self.close()
            raise


    def poll_write(self):
        """Returns True if we need to poll the file for write availability."""

        return True


    def on_write(self):
        """Called when we are able to write."""

        if self._write():
            self.close()


    def __on_timed_out(self):
        """Called on request timeout."""

        LOG.warning("%s timed out.", self)
        self.close()
