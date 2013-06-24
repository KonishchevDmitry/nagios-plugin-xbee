"""Various system utilities."""

from __future__ import unicode_literals

import os

from pcore import bytes
from psys import eintr_retry


def read(fd, size):
    """Same as os.read() but guaranteed reads data size that was requested."""

    data = bytearray()

    while size > 0:
        read_bytes = eintr_retry(os.read)(fd, size)
        if len(read_bytes) < 1:
            raise EOFError()

        data.extend(read_bytes)
        size -= len(read_bytes)

    return bytes(data)
