"""Contains all logic for communication with XBee 868."""

from __future__ import unicode_literals

import errno
import logging
import os
import struct
import serial

from xbee_868.core import Error, LogicalError
from xbee_868.io_loop import IOObjectBase


_FRAME_DELIMITER = 0x7E
"""XBee 868 frame delimiter."""

_MAX_FRAME_SIZE = 100
"""
Maximum frame size limit - just to detect broken frames and not read a lot of
data which takes a lot of time before we get a checksum mismatch error.
"""


_STATE_FIND_FRAME_HEADER = "find-frame-header"
"""State for finding a frame header."""

_STATE_RECV_FRAME_HEADER = "receive-frame-header"
"""State for receiving a frame header."""

_STATE_RECV_FRAME_BODY = "receive-frame-body"
"""State for receiving a frame body."""


# TODO
_SENSORS = {}


LOG = logging.getLogger(__name__)



class _InvalidFrameError(Error):
    """Invalid frame error."""

    def __init__(self, *args, **kwargs):
        super(_InvalidFrameError, self).__init__(*args, **kwargs)



class _Sensor(IOObjectBase):
    """Represents a XBee 868 sensor."""

    def __init__(self, io_loop, device):
        # TODO
        self.__sensor = serial.Serial(device)
        self.__sensor.nonblocking()

        super(_Sensor, self).__init__(io_loop, self.__sensor)

        self.__skipped_bytes = 0
        self.__offset = None
        self.__frame_size = None

        self.__set_state(_STATE_FIND_FRAME_HEADER)
        # TODO
        _SENSORS[device] = self
        def remove_from_sensors():
            if device in _SENSORS:
                del _SENSORS[device]
        self.add_on_close_handler(remove_from_sensors)


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
        """
        Checks the read buffer for availability of the specified bytes of data
        (counting from current read offset).
        """

        if self.__offset + size > len(self._read_buffer):
            raise _InvalidFrameError("End of frame has been reached.")


    def __find_frame_header(self):
        """Finds a frame header."""

        if not self._read(1):
            return

        if self._read_buffer[0] == _FRAME_DELIMITER:
            LOG.debug("Found a frame delimiter. %s bytes has been skipped.", self.__skipped_bytes)
            self.__set_state(_STATE_RECV_FRAME_HEADER)
        else:
            self._clear_read_buffer()
            self.__skipped_bytes += 1
            if not self.__skipped_bytes % 100:
                LOG.debug("Skip %s bytes...", self.__skipped_bytes)


    def __handle_frame(self):
        """Handles a frame."""

        LOG.debug("Frame: %s", " ".join("{0:02x}".format(c) for c in self._read_buffer))

        self.__check_read_buffer(1)
        frame_type = self._read_buffer[self.__offset]
        self.__offset += 1

        if frame_type != 0x92:
            LOG.info("Got an unknown frame %#x. Skipping it.", frame_type)
            return

        frame = bytes(self._read_buffer)


        frame_format = b"!QH BB HB"
        self.__check_read_buffer(struct.calcsize(frame_format))

        address, network_address, \
        receive_options, samples_number, \
        digital_mask, analog_mask = \
            struct.unpack_from(frame_format, frame, offset=self.__offset)
        self.__offset += struct.calcsize(frame_format)

        LOG.info("Got a %#x frame:", frame_type)
        LOG.info("Source address: %016X.", address)
        LOG.info("Network address: %04X.", network_address)


        LOG.info("Digital channel mask: %s.", "{0:016b}".format(digital_mask))

        if digital_mask:
            digital_samples_format = b"!H"
            digital_samples, = struct.unpack_from(
                digital_samples_format, frame, offset=self.__offset)
            self.__offset += struct.calcsize(digital_samples_format)

            LOG.info("Digital samples: %s.", "{0:016b}".format(digital_samples))


        LOG.info("Analog channel mask: %s.", "{0:08b}".format(analog_mask))

        analog_sample_format = b"!H"
        analog_sample_size = struct.calcsize(analog_sample_format)
        analog_mask_shift = 0

        while analog_mask:
            if analog_mask & 1:
                self.__check_read_buffer(analog_sample_size)
                analog_sample, = struct.unpack_from(
                    analog_sample_format, frame, offset=self.__offset)
                self.__offset += analog_sample_size

                LOG.info("Analog sample for %s: %04X.",
                    "{0:08b}".format(1 << analog_mask_shift), analog_sample)

            analog_mask >>= 1
            analog_mask_shift += 1


        if self.__offset != len(self._read_buffer) - 1: # -1 for checksum
            raise _InvalidFrameError("Frame size is too big for its payload.")


    def __handle_frame_error(self, error):
        """Handles a frame error."""

        LOG.error("Error while processing a frame: %s", error)

        frame_delimiter_pos = self._read_buffer.find(chr(_FRAME_DELIMITER), 1)

        if frame_delimiter_pos == -1:
            self.__skipped_bytes = len(self._read_buffer)
            self._clear_read_buffer()
            self.__set_state(_STATE_FIND_FRAME_HEADER)
        else:
            LOG.debug("Found a frame delimiter. %s bytes has been skipped.", frame_delimiter_pos)
            del self._read_buffer[:frame_delimiter_pos]
            self.__set_state(_STATE_RECV_FRAME_HEADER)


    def __receive_frame_body(self):
        """Receives frame body."""

        # Receive frame + checksum
        if not self._read(self.__offset + self.__frame_size + 1):
            return

        checksum = 0xFF - ( sum(byte for byte in self._read_buffer[3:-1]) & 0b11111111 )
        frame_checksum = self._read_buffer[-1]

        try:
            if checksum != frame_checksum:
                raise _InvalidFrameError("Frame checksum mismatch.")

            self.__handle_frame()
        except _InvalidFrameError as e:
            self.__handle_frame_error(e)
        else:
            self._clear_read_buffer()
            self.__set_state(_STATE_RECV_FRAME_HEADER)


    def __receive_frame_header(self):
        """Receives frame header."""

        header_format = b"!BH"
        header_size = struct.calcsize(header_format)

        if not self._read(header_size):
            return

        frame_delimiter, self.__frame_size, = struct.unpack(
            header_format, bytes(self._read_buffer))

        if frame_delimiter != _FRAME_DELIMITER:
            self.__handle_frame_error("Got an invalid frame delimiter.")
        elif self.__frame_size > _MAX_FRAME_SIZE:
            self.__handle_frame_error("Got a too big frame size.")
        else:
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



# TODO
def connect(io_loop):
    """Connects to XBee 868 devices."""

    device_name = "XBee 868"

    LOG.debug("Looking for %s devices...", device_name)

    devices = []
    device_directory = "/dev/serial/by-id"

    try:
        for device in os.listdir(device_directory):
            if "xbib-u-ss" in device.lower():
                devices.append(os.path.join(device_directory, device))
    except OSError as e:
        if e.errno == errno.ENOENT:
            LOG.error("There is no any connected serial device.")
        else:
            LOG.error("Unable to list connected serial devices: {0}.", e.strerror)
    else:
        for device in devices:
            if device not in _SENSORS:
                LOG.debug("Connecting to %s...", device)

                try:
                    _Sensor(io_loop, device)
                except Exception as e:
                    LOG.error("Failed to connect to %s: %s", device_name, e)

        if not devices and not _SENSORS:
            LOG.error("There is no any connected %s device.", device_name)

