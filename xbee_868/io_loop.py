# TODO FIXME
"""
Provides a main loop for handling I/O operations and various base classes for
handling I/O operations.
"""

import errno
import logging
import os
import select
import socket
import time

from psys import eintr_retry

class Error(Exception):
    """The base class for all exceptions that our code throws."""

    def __init__(self, error, *args):
        Exception.__init__(self, unicode(error).format(*args) if len(args) else unicode(str(error)))
        self.code = "Error"



class LogicalError(Exception):
    """Thrown in all code that must not be executed."""

    def __init__(self):
        Exception.__init__(self, "Logical error.")

LOG = logging.getLogger("c2." + __name__)


class IOLoop(object):
    """Main loop for handling I/O operations."""

    __epoll = None
    """A epoll object."""

    __objects = None
    """I/O objects that we are polling."""


    def __init__(self):
        self.__objects = {}
        self.__epoll = select.epoll()


    def __del__(self):
        if self.__epoll is not None:
            eintr_retry(self.__epoll.close)()


    def add_object(self, obj):
        """Adds an object to the list of polling objects."""

        try:
            self.__epoll.register(obj.file.fileno(), obj.epoll_flags)
        except Exception as e:
            raise Error("Unable to register a epoll descriptor: {0}.", e)

        self.__objects[obj.file.fileno()] = obj


    def remove_object(self, obj):
        """Removes an object from the list of polling objects."""

        try:
            try:
                del self.__objects[obj.file.fileno()]
            except KeyError:
                raise Error("it hasn't been added to the polling list")

            self.__epoll.unregister(obj.file.fileno())
        except Exception as e:
            LOG.error("Unable to remove a file descriptor: %s.", e)


    def start(self, precision=1):
        """Starts the main loop."""

        read_flags = select.EPOLLIN
        write_flags = select.EPOLLOUT

        while True:
            for fd, obj in self.__objects.items():
                cur_flags = 0

                if obj.timed_out():
                    obj.on_timeout()

                    if obj.closed():
                        continue

#				if self.should_stop():
#					obj.stop()
#
#					if obj.closed():
#						continue

                if obj.poll_read():
                    cur_flags |= read_flags

                if obj.poll_write():
                    cur_flags |= write_flags

                if obj.epoll_flags != cur_flags:
                    self.__epoll.modify(fd, cur_flags)
                    obj.epoll_flags = cur_flags

            if not self.__objects:
                break

            for fd, flags in self.__epoll.poll(timeout=precision):
                obj = self.__objects.get(fd)
                if obj is None:
                    continue

                if flags & read_flags:
                    if not obj.closed():
                        obj.on_read()

                if flags & write_flags:
                    if not obj.closed():
                        obj.on_write()


#	def should_stop(self):
#		"""Returns True if we should stop the loop."""
#
#		raise Error("Not implemented.")



class IOObjectBase(object):
    """Wraps a main loop object."""

    io_loop = None
    """I/O loop that controls the object."""

    file = None
    """File that we are polling."""

    epoll_flags = 0
    """epoll flags that are currently used for this object."""

    __timed_out_at = None
    """
    If set and current time is greater than the timed_out_at the object is
    considered as timed out.
    """

    __close_handlers = None
    """A list of handlers that will be called on object close."""


    _read_buffer = None


    def __init__(self, io_loop, file, session_timeout=None):
        self.io_loop = io_loop
        self.file = file
        self.__close_handlers = []

        if session_timeout is not None:
            self.__timed_out_at = time.time() + session_timeout

        self._read_buffer = bytearray()

        self.io_loop.add_object(self)


    def __del__(self):
        self.close()


    def add_on_close_handler(self, handler):
        """Adds a handler that will be called on object close."""

        self.__close_handlers.append(handler)


    def close(self):
        """Closes the I/O object."""

        if not self.closed():
            self.io_loop.remove_object(self)

            try:
                eintr_retry(self.file.close)()
            except Exception as e:
                LOG.error("Failed to close a file descriptor: %s.", e)

            self.file = None

            for handler in self.__close_handlers:
                try:
                    handler()
                except:
                    LOG.exception("A close handler crashed.")

        self.__close_handlers = []


    def closed(self):
        """Returns True if the object is closed."""

        return self.file is None


    def poll_read(self):
        """Returns True if we need to poll the socket for read availability."""

        return False


    def poll_write(self):
        """Returns True if we need to poll the socket for write availability."""

        return False


    def remove_on_close_handler(self, handler):
        """Adds a handler that will be called on object close."""

        try:
            self.__close_handlers.append(handler)
        except ValueError:
            LOG.error("Unable to remove an on close handler: there is not such handler.")


    def stop(self):
        """Called when the main loop ends its work.

        The object have to close itself in the near future after this call to
        allow the main loop to stop.
        """


    def timed_out(self):
        """Returns True if the object is timed out."""

        return self.__timed_out_at is not None and time.time() >= self.__timed_out_at


    def _read(self, size):
        if len(self._read_buffer) < size:
            data = eintr_retry(os.read)(self.file.fileno(), size - len(self._read_buffer))
            if not data:
                raise Exception("TODO FIXME")
            self._read_buffer.extend(data)
        return len(self._read_buffer) == size

    def _clear_read_buffer(self):
        del self._read_buffer[:]





class TCPSockBase(IOObjectBase):
    """A base class for handling TCP sockets."""

    def __init__(self, io_loop, sock, *args, **kwargs):
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)

        super(TCPSockBase, self).__init__(io_loop, sock, *args, **kwargs)


    def get_errno(self):
        """Returns current socket error."""

        try:
            return self.file.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        except EnvironmentError as e:
            return e.errno


    def _accept(self):
        """Accepts a TCP connection."""

        try:
            return eintr_retry(self.file.accept)()
        except EnvironmentError as e:
            if e.errno == errno.ECONNABORTED:
                pass
            else:
                raise


    def _bind(self, port):
        """Binds the socket to the specified port."""

        self.file.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.file.bind(( "0.0.0.0", port ))


    def _connect(self, *args):
        """Connects to the specified host."""

        try:
            eintr_retry(self.file.connect)(*args)
        except EnvironmentError as e:
            if e.errno != errno.EINPROGRESS:
                raise


    def _listen(self):
        """Makes the socket listening."""

        self.file.listen(config.LISTEN_BACKLOG)



class TCPAcceptor(TCPSockBase):
    """A base class for accepting TCP connections."""

    def __init__(self, io_loop, port=None, sock=None):
        if (port is None) + (sock is None) != 1:
            raise LogicalError()

        super(TCPAcceptor, self).__init__(io_loop, sock)

        try:
            if port is not None:
                self._bind(port)
                self._listen()
        except:
            self.close()
            raise


    def on_error(self, e):
        """Called on error."""

        LOG.error("Error while handling a listening connection: %s.", e)
        self.close()


    def on_read(self):
        """Called when we have data to read."""

        try:
            connection = self._accept()
        except Exception as e:
            LOG.error("Unable to accept a connection: %s.", e)
            self.close()
        else:
            if connection is not None:
                self.connection_accepted(*connection)


    def poll_read(self):
        """Returns True if we need to poll the socket for read availability."""

        return True
