"""Contains all logic for communication with XBee 868."""

from __future__ import unicode_literals

import logging
import struct
import serial

from xbee_868.core import LogicalError
from xbee_868.io_loop import IOObjectBase


_FRAME_DELIMITER = 0x7E
"""XBee 868 frame delimiter."""


_STATE_FIND_FRAME_HEADER = "find-frame-header"
"""State for finding a frame header."""

_STATE_RECV_FRAME_HEADER = "receive-frame-header"
"""State for receiving a frame header."""

_STATE_RECV_FRAME_BODY = "receive-frame-body"
"""State for receiving a frame body."""


LOG = logging.getLogger(__name__)


class Sensor(IOObjectBase):
    """Represents a XBee 868 sensor."""

    def __init__(self, io_loop):
        # TODO
        self.__sensor = serial.Serial("/dev/ttyUSB0")
        self.__sensor.nonblocking()

        super(Sensor, self).__init__(io_loop, self.__sensor)

        self.__set_state(_STATE_FIND_FRAME_HEADER)

        self.__offset = None
        self.__frame_size = None


    def on_read(self):
        """Called when we have data to read."""

        if self.__state == _STATE_FIND_FRAME_HEADER:
            self.__find_frame_header()
        elif self.__state == _STATE_RECV_FRAME_HEADER:
            self.__receive_frame_header()
        elif self.__state == _STATE_RECV_FRAME_BODY:
            self.__receive_frame_body()
        else:
            raise LogicalError()


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


    def __check_read_buffer(self, size):
        # TODO
        assert self.__offset + size <= len(self._read_buffer)


    def __find_frame_header(self):
        """Finds a frame header."""

        # TODO: limits
        if not self._read(len(self._read_buffer) + 1):
            return

        if self._read_buffer[-1] == _FRAME_DELIMITER:
            LOG.debug("Found a frame delimiter.")
            del self._read_buffer[:-1]
            self.__set_state(_STATE_RECV_FRAME_HEADER)
        else:
            LOG.debug("Skip %s bytes...", len(self._read_buffer))


    def __handle_frame(self):
        """Handles a frame."""

        self.__check_read_buffer(1)
        frame_type = self._read_buffer[self.__offset]

        if frame_type == 0x92:
            LOG.debug("Frame: %s", " ".join("{0:x}".format(c) for c in self._read_buffer))
            #frame_format = "!QHBBHB"
            #assert offset + struct.calcsize(frame_format) < len(frame)

            #address, network_address, \
            #receive_options, samples_number, \
            #digital_mask, analog_mask = \
            #    struct.unpack_from(frame_format, frame, offset=offset)

            #print "Address:", "{0:016X}".format(address)
            #print "Network address:", "{0:04X}".format(network_address)
            #print "Digital mask:", hex(digital_mask)
            #print "Analog mask:", hex(analog_mask)
            #offset += struct.calcsize(frame_format)

            #if digital_mask:
            #    offset += 2

            #analog_data_format = "!H"
            #analog_mask_shift = 0
            #while analog_mask:
            #    if analog_mask & 1:
            #        assert offset + struct.calcsize(analog_data_format) <= len(frame)
            #        analog_data, = struct.unpack_from(analog_data_format, frame, offset=offset)
            #        offset += struct.calcsize(analog_data_format)

            #        print "Analog data for", 1 << analog_mask_shift, ":", hex(analog_data)
            #    analog_mask_shift += 1
            #    analog_mask >>= 1
            #frame = bytes(self._read_buffer)

            # TODO FIXME
            #assert self.__offset == self.__frame_size
        else:
            LOG.info("Got an unknown frame [%#x]. Skipping it.", frame_type)


    def __receive_frame_body(self):
        """Receives frame body."""

        # Receive frame + checksum
        if not self._read(self.__offset + self.__frame_size + 1):
            return

        checksum = 0xFF - ( sum(byte for byte in self._read_buffer[3:-1]) & 0b11111111 )
        frame_checksum = self._read_buffer[-1]
        # TODO
        assert checksum == frame_checksum

        self.__handle_frame()

        self._clear_read_buffer()
        self.__set_state(_STATE_RECV_FRAME_HEADER)


    def __receive_frame_header(self):
        """Receives frame header."""

        header_format = b"!BH"
        header_size = struct.calcsize(header_format)

        if not self._read(header_size):
            return

        # TODO: limits
        frame_delimiter, self.__frame_size, = struct.unpack(
            header_format, bytes(self._read_buffer))

        # TODO
        assert frame_delimiter == _FRAME_DELIMITER

        self.__offset = header_size

        LOG.debug("Got a frame of %s bytes.", self.__frame_size)
        self.__set_state(_STATE_RECV_FRAME_BODY)


    def __set_state(self, state):
        """Sets current state."""

        if state == _STATE_FIND_FRAME_HEADER:
            LOG.debug("Looking for a frame header...")
        elif state == _STATE_RECV_FRAME_HEADER:
            LOG.debug("Receiving a frame header...")
        elif state == _STATE_RECV_FRAME_BODY:
            LOG.debug("Receiving a frame body...")
        else:
            raise LogicalError()

        self.__state = state
