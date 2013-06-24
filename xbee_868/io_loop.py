# TODO FIXME
"""
Provides a main loop for handling I/O operations and various base classes for
handling I/O operations.
"""

import bisect
import errno
import logging
import os
import select
import socket
import time

from psys import eintr_retry
from xbee_868.core import Error, LogicalError


LOG = logging.getLogger(__name__)


class IoLoop(object):
    """Main loop for handling I/O operations."""

    # TODO FIXME
    __epoll = None
    """A epoll object."""

    __objects = None
    """I/O objects that we are polling."""


    def __init__(self):
        self.__objects = {}
        self.__epoll = select.epoll()
        self.__activate_at = []


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


    def call(self, func, *args, **kwargs):
        return self.call_at(0, func, *args, **kwargs)
    def call_after(self, timeout, func, *args, **kwargs):
        return self.call_at(time.time() + timeout, func, *args, **kwargs)
    def call_at(self, activate_time, func, *args, **kwargs):
        call = (activate_time, func, args, kwargs)
        self.__activate_at.insert(
            bisect.bisect([task[0] for task in self.__activate_at], activate_time),
            call)
        return call
    def cancel_call(self, task):
        self.__activate_at = [ t for t in self.__activate_at if task is not t ]

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

#            if not self.__objects:
#                break

            timeout = -1
            if self.__activate_at:
                timeout = max(0, self.__activate_at[0][0] - time.time())

            for fd, flags in self.__epoll.poll(timeout=timeout):
                obj = self.__objects.get(fd)
                if obj is None:
                    continue

                if flags & read_flags:
                    if not obj.closed():
                        obj.on_read()

                if flags & write_flags:
                    if not obj.closed():
                        obj.on_write()

                # TODO
                if flags & select.EPOLLHUP:
                    if not obj.closed():
                        obj.on_hang_up()

                # TODO
                if flags & select.EPOLLERR:
                    if not obj.closed():
                        # TODO
                        obj.on_error()

            drop_index = None
            cur_time = time.time()
            for task_id, task in enumerate(self.__activate_at[:]):
                if task[0] <= cur_time:
                    drop_index = task_id
                else:
                    break

            if drop_index is not None:
                calls = self.__activate_at[:drop_index + 1]
                del self.__activate_at[:drop_index + 1]
                for task in calls:
                    # TODO: dicts + exceptions
                    task[1](*task[2], **task[3])


#	def should_stop(self):
#		"""Returns True if we should stop the loop."""
#
#		raise Error("Not implemented.")



class FileObject(object):
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
    _write_buffer = None


    def __init__(self, io_loop, file, session_timeout=None):
        self.io_loop = io_loop
        self.file = file
        self.__close_handlers = []

        if session_timeout is not None:
            self.__timed_out_at = time.time() + session_timeout

        self._read_buffer = bytearray()
        self._write_buffer = bytearray()

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


    def on_error(self):

        TODO

    def on_read(self):
        """Called when we have data to read."""

        TODO

    def on_write(self):
        """Called when we are able to write."""

        TODO

    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return False


    def poll_write(self):
        """Returns True if we need to poll the file for write availability."""

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
            # TODO: EWOULDBLOCK
            data = eintr_retry(os.read)(self.file.fileno(), size - len(self._read_buffer))
            if not data:
                raise Exception("TODO FIXME")
            self._read_buffer.extend(data)
        return len(self._read_buffer) == size

    def _write(self, data=None):
        if data is not None:
            self._write_buffer.extend(data)

        if self._write_buffer:
            # TODO: EWOULDBLOCK
            size = eintr_retry(os.write)(self.file.fileno(), self._write_buffer)
            if size:
                del self._write_buffer[:size + 1]

        return not self._write_buffer
    def _clear_read_buffer(self):
        del self._read_buffer[:]
