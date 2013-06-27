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

from xbee.common import constants
from xbee.common.core import Error
from xbee.common.io_loop import FileObject

import xbee.monitor.request
from xbee import monitor

xbee # Suppress PyFlakes warnings

_MAX_REQUEST_SIZE = 1024 * 1024
"""Maximum request size."""

LOG = logging.getLogger(__name__)


class Server(FileObject):
    """The monitor server socket."""

    def __init__(self, io_loop):
        self.__client_id = 0

        path = constants.SERVER_SOCKET_PATH
        LOG.info("Listening to client connections at '%s'...", path)

        self.__delete_socket()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.setblocking(False)

            try:
                sock.bind(path)
                sock.listen(128)
            except EnvironmentError as e:
                raise Error("Unable to create a UNIX socket '{0}': {1}.", path, e)

            super(Server, self).__init__(io_loop, sock, "Monitor's server socket")
        except:
            try:
                self.__delete_socket()
            except Exception as e:
                LOG.error(e)

            eintr_retry(sock.close())

            raise


    def close(self):
        """Closes the object."""

        if not self.closed():
            try:
                self.__delete_socket()
            except Exception as e:
                LOG.error("Error while closing the server socket: %s", e)

        super(Server, self).close()


    def stop(self):
        """Called when the I/O loop ends its work."""

        self.close()


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


    def on_read(self):
        """Called when we have data to read."""

        try:
            connection = eintr_retry(self._file.accept)()[0]
        except EnvironmentError as e:
            if e.errno != errno.ECONNABORTED:
                LOG.error("Unable to accept a connection: %s.", e)
        else:
            connection_name = "Client connection #{0}".format(self.__client_id)
            self.__client_id += 1

            LOG.debug("Accepting a new %s...", connection_name)

            try:
                _Client(self._weak_io_loop(), connection, connection_name)
            except Exception as e:
                LOG.error("Failed to accept %s: %s.", connection_name, e)
                eintr_retry(connection.close())


    def __delete_socket(self):
        """Deletes the server socket."""

        path = constants.SERVER_SOCKET_PATH

        try:
            os.unlink(path)
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise Error("Unable to delete '{0}': {1}.", path)



class _Client(FileObject):
    """A client connection socket."""

    __message_size_format = b"!Q"
    """Format of the message size."""

    __message_size = None
    """Request message size."""

    __got_request = False
    """Did we get a request?"""


    def __init__(self, io_loop, sock, name):
        sock.setblocking(False)
        super(_Client, self).__init__(io_loop, sock, name)

        try:
            self.add_deferred_call(
                io_loop.call_after(constants.IPC_TIMEOUT, self.__on_timed_out))
        except Exception:
            self.close()
            raise


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return not self.__got_request


    def poll_write(self):
        """Returns True if we need to poll the file for write availability."""

        return self.__got_request


    def on_read(self):
        """Called when we are able to read."""

        if self.__message_size is None:
            if self._read(struct.calcsize(self.__message_size_format)):
                self.__message_size, = struct.unpack(
                    self.__message_size_format, bytes(self._read_buffer))
                self._clear_read_buffer()

                if self.__message_size > _MAX_REQUEST_SIZE:
                    self.on_error("Too big message size has been gotten ({0}).",
                        self.__message_size)
        else:
            if self._read(self.__message_size):
                self.__got_request = True
                self.__handle_request()


    def on_write(self):
        """Called when we are able to write."""

        if self._write():
            self.close()


    def __on_timed_out(self):
        """Called on request timeout."""

        LOG.warning("%s timed out.", self)
        self.close()


    def __handle_request(self):
        """Handles a request."""

        try:
            request = json.loads(self._read_buffer.decode("utf-8"))

            if (
                "method" not in request or
                any(type(key) is not str for key in request.keys()) or
                any(type(value) is not str for value in request.values())
            ):
                raise ValueError()
        except (UnicodeDecodeError, ValueError):
            LOG.error("%s: got an invalid request %s.", self, bytes(self._read_buffer))
            self.close()
            return

        LOG.info("%s: request %s", self, request)

        try:
            reply = { "result": monitor.request.handle(request.pop("method"), request) }
        except Exception as e:
            (LOG.warning if isinstance(e, Error) else LOG.error)(
                "%s: request failed: %s", self, e)

            reply = { "error": str(e) if isinstance(e, Error) else "Internal error" }

        response = json.dumps(reply).encode("utf-8")
        if self._write(struct.pack(self.__message_size_format, len(response)) + response):
            self.close()
