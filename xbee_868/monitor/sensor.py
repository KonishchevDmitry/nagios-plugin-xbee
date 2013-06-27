"""Contains all logic for communication with XBee 868."""

from __future__ import unicode_literals

import errno
import logging
import os
import struct
# TODO
#import serial

from pcore import PY3

from xbee_868.common.core import Error, LogicalError
from xbee_868.common.io_loop import FileObject

import xbee_868.monitor.stats
from xbee_868.monitor import config
from xbee_868 import monitor

xbee_868 # Suppress PyFlakes warnings


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


LOG = logging.getLogger(__name__)



class _InvalidFrameError(Error):
    """Invalid frame error."""

    def __init__(self, *args, **kwargs):
        super(_InvalidFrameError, self).__init__(*args, **kwargs)



class _Sensor(FileObject):
    """Represents a XBee 868 sensor."""

    sensors = set()
    """All opened devices."""


    def __init__(self, io_loop, device):
        # TODO
        #sensor = serial.Serial(device, baudrate=9600)
        sensor = open(device, "r")
        import fcntl
        fcntl.fcntl(sensor.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

        try:
            # TODO
            #sensor.nonblocking()
            super(_Sensor, self).__init__(
                io_loop, sensor, "XBee 868 at " + device)
        except:
            sensor.close()
            raise

        try:
            self.__offset = None
            self.__skipped_bytes = 0
            self.__frame_size = None
            self.__set_state(_STATE_FIND_FRAME_HEADER)

            self.add_on_close_handler(lambda: self.sensors.discard(device))
            self.sensors.add(device)
        except:
            self.close()
            raise



    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


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



    def stop(self):
        """Called when the I/O loop ends its work."""

        self.close()



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


    def __handle_frame(self):
        """Handles a frame."""

        LOG.debug("Frame: %s", " ".join("{0:02x}".format(c) for c in self._read_buffer))

        self.__check_read_buffer(1)
        frame_type = self._read_buffer[self.__offset]
        self.__offset += 1

        if frame_type == 0x92:
            self.__handle_metrics_frame()
        else:
            LOG.debug("Got an unknown frame %#x. Skipping it.", frame_type)


    def __handle_metrics_frame(self):
        """Handles a metrics frame."""

        frame = bytes(self._read_buffer)

        frame_format = b"!QH BB HB"
        self.__check_read_buffer(struct.calcsize(frame_format))

        address, network_address, \
        receive_options, samples_number, \
        digital_mask, analog_mask = \
            struct.unpack_from(frame_format, frame, offset=self.__offset)
        self.__offset += struct.calcsize(frame_format)

        LOG.debug("Got a metrics frame:")
        LOG.debug("Source address: %016X.", address)
        LOG.debug("Network address: %04X.", network_address)


        LOG.debug("Digital channel mask: %s.", "{0:016b}".format(digital_mask))

        if digital_mask:
            digital_samples_format = b"!H"
            digital_samples, = struct.unpack_from(
                digital_samples_format, frame, offset=self.__offset)
            self.__offset += struct.calcsize(digital_samples_format)

            LOG.debug("Digital samples: %s.", "{0:016b}".format(digital_samples))


        LOG.debug("Analog channel mask: %s.", "{0:08b}".format(analog_mask))

        metrics = {}
        analog_sample_format = b"!H"
        analog_sample_size = struct.calcsize(analog_sample_format)
        analog_mask_shift = 0

        while analog_mask:
            if analog_mask & 1:
                self.__check_read_buffer(analog_sample_size)
                analog_sample, = struct.unpack_from(
                    analog_sample_format, frame, offset=self.__offset)
                self.__offset += analog_sample_size

                LOG.debug("Analog sample for %s: %04X.",
                    "{0:08b}".format(1 << analog_mask_shift), analog_sample)

                metrics[analog_mask_shift] = analog_sample

            analog_mask >>= 1
            analog_mask_shift += 1


        if self.__offset != len(self._read_buffer) - 1: # -1 for checksum
            raise _InvalidFrameError("Frame size is too big for its payload.")


        try:
            host = config.ADDRESSES[address]
        except KeyError:
            LOG.warning("Got metrics for an unknown MAC address: %016X.", address)
        else:
            _handle_temperature(host, metrics.get(1))


    def __check_read_buffer(self, size):
        """
        Checks the read buffer for availability of the specified bytes of data
        (counting from current read offset).
        """

        if self.__offset + size > len(self._read_buffer):
            raise _InvalidFrameError("End of frame has been reached.")


    def __handle_frame_error(self, error):
        """Handles a frame error."""

        LOG.error("Error while processing a frame: %s", error)

        frame_delimiter_pos = self._read_buffer.find(
            _FRAME_DELIMITER if PY3 else chr(_FRAME_DELIMITER), 1)

        if frame_delimiter_pos == -1:
            self.__skipped_bytes = len(self._read_buffer)
            self._clear_read_buffer()
            self.__set_state(_STATE_FIND_FRAME_HEADER)
        else:
            LOG.debug("Found a frame delimiter. %s bytes has been skipped.", frame_delimiter_pos)
            del self._read_buffer[:frame_delimiter_pos]
            self.__set_state(_STATE_RECV_FRAME_HEADER)



def connect(io_loop):
    """Connects to XBee 868 devices."""

    device_name = "XBee 868"
    device_directory = "/dev/serial/by-id"

    LOG.debug("Looking for %s devices...", device_name)

    try:
        devices = [
            os.path.join(device_directory, device)
            for device in os.listdir(device_directory)
                if "xbib-u-ss" in device.lower()
        ]
    except OSError as e:
        if e.errno == errno.ENOENT:
            LOG.debug("There is no any connected serial devices.")
        else:
            LOG.error("Unable to list connected serial devices: {0}.", e.strerror)
    else:
        for device in devices:
            if device not in _Sensor.sensors:
                LOG.info("Connecting to %s at %s...", device_name, device)

                try:
                    _Sensor(io_loop, device)
                except Exception as e:
                    LOG.error("Failed to connect to %s: %s", device_name, e)

        if not devices:
            LOG.debug("There is no any connected %s device.", device_name)


def _handle_temperature(host, value):
    """Handles a temperature metric."""

    max_value = 1023
    max_voltage = 2.5

    if value in (None, max_value):
        LOG.warning("%s doesn't have a temperature sensor.", host)
    elif value < max_value:
        voltage = float(value) / max_value * max_voltage
        degrees = int((voltage - 0.5) * 100)
        LOG.info("Got a temperature for %s: %s.", host, degrees)
        monitor.stats.add_metric(host, "temperature", degrees)
    else:
        LOG.error("Got an invalid temperature value for %s.", host)
