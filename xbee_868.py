import struct
import serial

sensor = serial.Serial("/dev/ttyUSB0")

STATE_RECV_FRAME_HEADER = "header"

STATE_RECV_FRAME_BODY = "frame"

state = STATE_RECV_FRAME_HEADER
header_format = "!BH"
frame_format = "!QHBBHB"
analog_data_format = "!H"

while True:
    while True:
        if state == STATE_RECV_FRAME_HEADER:
            print
            header = sensor.read(struct.calcsize(header_format))
            frame_delimiter, frame_size = struct.unpack(header_format, header)
            print "Frame delimiter:", hex(frame_delimiter)
            print "Frame size:", hex(frame_size)
            assert frame_delimiter == 0x7E
            state = STATE_RECV_FRAME_BODY
        elif state == STATE_RECV_FRAME_BODY:
            offset = 0
            frame = sensor.read(frame_size + 1)


            assert offset + 1 <= len(frame)
            frame_type = ord(frame[0])
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


            print "Frame:", " ".join(hex(ord(c)) for c in frame)

            checksum = 0xFF - (sum(ord(c) for c in frame[:offset])) & 0b11111111

            assert offset + 1 <= len(frame)
            frame_checksum = ord(frame[offset])
            offset += 1

            assert offset == len(frame)

            print "Checksum:", hex(checksum)
            print "Checksum:", hex(frame_checksum)
            assert checksum == frame_checksum

            state = STATE_RECV_FRAME_HEADER
        else:
            TODO
