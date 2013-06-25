"""Provides a I/O main loop framework."""

from __future__ import unicode_literals

import bisect
import errno
import logging
import os
import select
import time
import weakref

from collections import namedtuple
from select import EPOLLIN, EPOLLOUT, EPOLLHUP, EPOLLERR

from pcore import PY3, range
from psys import eintr_retry

from xbee_868.core import Error

LOG = logging.getLogger(__name__)


class IoLoop(object):
    """Main loop for handling I/O operations."""

    def __init__(self):
        # Polled objects
        self.__objects = {}

        # epoll flags cache
        self.__epoll_flags = {}

        # A list of scheduled deferred calls
        self.__deferred_calls = []

        self.__epoll = select.epoll()


    def close(self):
        """Closes the object."""

        eintr_retry(self.__epoll.close)()



    def add_object(self, obj):
        """Adds an object to the list of polled objects."""

        try:
            self.__epoll.register(obj.fileno(), 0)
        except Exception as e:
            raise Error("Unable to register a file descriptor in epoll: {0}.", e)

        self.__objects[obj.fileno()] = obj


    def remove_object(self, obj):
        """Removes an object from the list of polled objects."""

        try:
            fileno = obj.fileno()

            if fileno in self.__objects:
                self.__epoll.unregister(fileno)
                del self.__objects[fileno]

                try:
                    del self.__epoll_flags[fileno]
                except KeyError:
                    pass
        except Exception as e:
            LOG.error("Failed to remove %s from the I/O loop: %s.", e)



    def call_at(self, call_time, func, *args, **kwargs):
        """Schedule a deferred call."""

        call = _DeferCall(call_time, lambda: func(*args, **kwargs))

        self.__deferred_calls.insert(
            bisect.bisect(self.__deferred_calls, call), call)

        return call


    def call_after(self, interval, func, *args, **kwargs):
        """A shortcut for call_at()."""

        return self.call_at(time.time() + interval, func, *args, **kwargs)


    def call_next(self, func, *args, **kwargs):
        """A shortcut for call_at()."""

        return self.call_at(0, func, *args, **kwargs)


    def cancel_call(self, call):
        """Cancels the specified deferred call."""

        for call_id in range(len(self.__deferred_calls)):
            if self.__deferred_calls[call_id] is call:
                del self.__deferred_calls[call_id]
                return



    def start(self):
        """Starts the I/O loop."""

        LOG.debug("Start the I/O loop.")

        while self.__objects or self.__deferred_calls:
            self.__update_epoll_flags()
            self.__poll_objects()
            self.__process_deferred_calls()

        LOG.debug("The I/O loop stopped.")


    def stop(self):
        """Stops the I/O loop."""

        LOG.debug("Stopping the I/O loop...")

        for obj in list(self.__objects.values()):
            try:
                obj.stop()
            except Exception:
                LOG.exception("Failed to stop %s.", obj)



    def __update_epoll_flags(self):
        """Updates epoll flags for all polled objects."""

        for fd, obj in self.__objects.items():
            try:
                obj_flags = 0

                if obj.poll_read():
                    obj_flags |= EPOLLIN

                if obj.poll_write():
                    obj_flags |= EPOLLOUT

                if self.__epoll_flags.get(fd, 0) != obj_flags:
                    self.__epoll.modify(fd, obj_flags)
                    self.__epoll_flags[fd] = obj_flags
            except Exception:
                LOG.exception("Error while configuring epoll for %s.", obj)


    def __poll_objects(self):
        """Polls the controlled objects."""

        timeout = -1
        if self.__deferred_calls:
            timeout = max(0, self.__deferred_calls[0].time - time.time())

        # TODO
        LOG.debug("Sleep with %s timeout...", timeout)
        for fd, flags in eintr_retry(self.__epoll.poll)(timeout=timeout):
            try:
                obj = self.__objects[fd]
            except KeyError:
                continue

            try:
                if flags & EPOLLIN:
                    if not obj.closed():
                        obj.on_read()

                if flags & EPOLLOUT:
                    if not obj.closed():
                        obj.on_write()

                if flags & EPOLLHUP:
                    if not obj.closed():
                        obj.on_hang_up()

                if flags & EPOLLERR:
                    if not obj.closed():
                        obj.on_error(Error("epoll returned an error state."))
            except Exception as e:
                if not isinstance(e, OSError):
                    LOG.exception("%s handling crashed.", obj)

                obj.on_error(e)


    def __process_deferred_calls(self):
        """Processes pending deferred calls."""

        if not self.__deferred_calls:
            return

        cur_time = time.time()
        precision = 0.001

        for call_id in range(len(self.__deferred_calls)):
            if self.__deferred_calls[call_id].time - precision > cur_time:
                pending_calls = self.__deferred_calls[:call_id]
                del self.__deferred_calls[:call_id]
                break
        else:
            pending_calls = self.__deferred_calls
            self.__deferred_calls = []

        for call in pending_calls:
            try:
                call.func()
            except Exception:
                LOG.exception("A deferred call crashed.")



class FileObject(object):
    """Represents a file object to connect to I/O loop."""

    def __init__(self, io_loop, file_obj, name):
        # I/O loop that controls the object
        self._weak_io_loop = weakref.ref(io_loop)

        # File that we are controlling
        self._file = file_obj

        # Name of the object
        self.__name = name

        # The object's read buffer
        self._read_buffer = bytearray()

        # The object's write buffer
        self._write_buffer = bytearray()

        # A list of handlers that will be called on object close
        self.__on_close_handlers = []

        io_loop.add_object(self)


    def close(self):
        """Closes the object."""

        if not self.closed():
            LOG.debug("Close %s.", self)

            io_loop = self._weak_io_loop()
            if io_loop is not None:
                io_loop.remove_object(self)

            try:
                eintr_retry(self._file.close)()
            except Exception as e:
                LOG.error("Failed to close %s: %s.", self, e)

            self._file = None

            for handler in self.__on_close_handlers:
                try:
                    handler()
                except:
                    LOG.exception("A close handler for %s crashed.", self)

        self.__on_close_handlers = []



    def fileno(self):
        """Returns the file descriptor."""

        return self._file.fileno()


    def closed(self):
        """Returns True if the object is closed."""

        return self._file is None



    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return False


    def poll_write(self):
        """Returns True if we need to poll the file for write availability."""

        return False



    def on_read(self):
        """Called when we got EPOLLIN event."""

        raise Error("Not implemented.")


    def on_write(self):
        """Called when we got EPOLLOUT event."""

        raise Error("Not implemented.")


    def on_hang_up(self):
        """Called when we got EPOLLHUP event."""

        LOG.debug("%s got a hang up.", self)
        self.close()


    def on_error(self, error):
        """Called when we got EPOLLERR event."""

        LOG.error("%s got an error: %s", self, error)
        self.close()



    def add_on_close_handler(self, handler):
        """Adds a handler that will be called on object close."""

        self.__on_close_handlers.append(handler)


    def add_deferred_call(self, call):
        """
        Associates a deferred call with this object to cancel it on object
        close.
        """

        def cancel_call():
            io_loop = self._weak_io_loop()
            if io_loop is not None:
                io_loop.cancel_call(call)

        self.add_on_close_handler(cancel_call)


    def stop(self):
        """Called when the I/O loop ends its work.

        The object have to close itself in the near future after this call to
        allow the I/O to stop.
        """



    def _clear_read_buffer(self):
        """Clears the read buffer."""

        del self._read_buffer[:]


    def _read(self, size):
        """
        Reads data from the file to the read buffer and returns True only when
        the specified size will be read.
        """

        if len(self._read_buffer) < size:
            try:
                data = eintr_retry(os.read)(self.fileno(), size - len(self._read_buffer))
            except OSError as e:
                if e.errno == errno.EWOULDBLOCK:
                    pass
                else:
                    raise
            else:
                if not data:
                    raise EOFError("End of file has been reached.")

                self._read_buffer.extend(data)

        return len(self._read_buffer) >= size


    def _write(self, data=None):
        """
        Writes the data from the write buffer + the specified data and returns
        True only when all the data will be written.
        """

        if data is not None:
            self._write_buffer.extend(data)

        if self._write_buffer:
            try:
                size = eintr_retry(os.write)(self.fileno(), self._write_buffer)
            except OSError as e:
                if e.errno == errno.EWOULDBLOCK:
                    pass
                else:
                    raise
            else:
                if size:
                    del self._write_buffer[:size + 1]

        return not self._write_buffer



    if PY3:
        def __str__(self):
            return self.__name
    else:
        def __unicode__(self):
            return self.__name



_DeferCall = namedtuple("DeferCall", ("time", "func"))
"""Represents a deferred call object."""
