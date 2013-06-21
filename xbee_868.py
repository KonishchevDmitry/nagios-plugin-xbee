import errno
import os
import select
import struct
import serial

import psys.poll
from psys import eintr_retry
from psys import bytes, str


frame_format = "!QHBBHB"
analog_data_format = "!H"


def read_nb(fd, size, all_data):
    if len(all_data) < size:
        data = eintr_retry(os.read)(fd, size - len(all_data))
        if not data:
            raise Exception("TODO FIXME")
        all_data.extend(data)
    return len(all_data) == size


from io_loop import IOLoop, IOObjectBase


class Sensor(IOObjectBase):
    STATE_RECV_FRAME_HEADER = "header"
    STATE_RECV_FRAME_BODY = "frame"

    def __init__(self, io_loop):
        # TODO FIXME
        self.__sensor = self.file = serial.Serial("/dev/ttyUSB0")
        self.__sensor.nonblocking()
        self.__data = bytearray()
        self.__state = self.STATE_RECV_FRAME_HEADER

        self.__offset = None
        self.__frame_size = None

        io_loop.add_object(self)


    def poll_read(self):
        """Returns True if we need to poll the file for read availability."""

        return True


    def on_read(self):
        if self.__state == self.STATE_RECV_FRAME_HEADER:
            print "HERE"
            header_format = "!BH"
            if read_nb(self.__sensor.fileno(), struct.calcsize(header_format), self.__data):
                frame_delimiter, self.__frame_size = struct.unpack(header_format, bytes(self.__data))
                print "Frame delimiter:", hex(frame_delimiter)
                print "Frame size:", hex(self.__frame_size)
                assert frame_delimiter == 0x7E
                del self.__data[:]
                self.__state = self.STATE_RECV_FRAME_BODY
        elif self.__state == self.STATE_RECV_FRAME_BODY:
            print "HERE2"
            if read_nb(self.__sensor.fileno(), self.__frame_size + 1, self.__data):
                frame = bytes(self.__data)
                offset = 0

                assert offset + 1 <= len(frame)
                frame_type = self.__data[0]
                offset += 1
                print "Frame type:", hex(frame_type)


                assert offset + struct.calcsize(frame_format) < len(frame)

                address, network_address, \
                receive_options, samples_number, \
                digital_mask, analog_mask = \
                    struct.unpack_from(frame_format, frame, offset=offset)

                print "Address:", "{0:016X}".format(address)
                print "Network address:", "{0:04X}".format(network_address)
                print "Digital mask:", hex(digital_mask)
                print "Analog mask:", hex(analog_mask)
                offset += struct.calcsize(frame_format)

                if digital_mask:
                    offset += 2

                analog_mask_shift = 0
                while analog_mask:
                    if analog_mask & 1:
                        assert offset + struct.calcsize(analog_data_format) <= len(frame)
                        analog_data, = struct.unpack_from(analog_data_format, frame, offset=offset)
                        offset += struct.calcsize(analog_data_format)

                        print "Analog data for", 1 << analog_mask_shift, ":", hex(analog_data)
                    analog_mask_shift += 1
                    analog_mask >>= 1


                print "Frame:", " ".join(hex(c) for c in self.__data)

                checksum = 0xFF - (sum(c for c in self.__data[:offset])) & 0b11111111

                assert offset + 1 <= len(frame)
                frame_checksum = self.__data[offset]
                offset += 1

                assert offset == len(frame)

                print "Checksum:", hex(checksum)
                print "Checksum:", hex(frame_checksum)
                assert checksum == frame_checksum

                del self.__data[:]
                self.__state = self.STATE_RECV_FRAME_HEADER
        else:
            TODO

# fcntl.fcntl(self.fd, FCNTL.F_SETFL, os.O_NONBLOCK)

io_loop = IOLoop()
Sensor(io_loop)
io_loop.start()
#poll = psys.poll.Poll()
#poll.register(sensor.fileno(), poll.POLLIN)

#try:
#    while True:
#        for fd, epoll_flags in poll.poll():
#            sensor.on_read()
#finally:
#    poll.close()
