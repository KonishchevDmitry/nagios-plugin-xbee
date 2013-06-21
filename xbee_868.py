import struct
import serial

sensor = serial.Serial("/dev/ttyUSB0")
while True:
    frame = ""

    while True:
        byte = sensor.read()

        if byte == "\x7e":
            if frame:
                print
                size, frame_type, address, network_address, \
                receive_options, samples_number, \
                digital_mask, analog_mask = \
                    struct.unpack_from("!HBQH" "BB" "HB", frame, offset=1)
                print "Size:", size
                print "Frame type:", hex(frame_type)
                print "Address:", "{0:016X}".format(address)
                print "Network address:", "{0:04X}".format(network_address)
                print "Digital mask:", hex(digital_mask)
                print "Analog mask:", hex(analog_mask)
                #struct.unpack_from(fmt, frame, offset=1)
                print " ".join(hex(ord(c)) for c in frame)
            frame = byte
        else:
            frame += byte
