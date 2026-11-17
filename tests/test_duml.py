import unittest

from gasfix.duml import Stream, parse_sticks, packet

# Constructed fixture with independently calculated checksums:
# right H=center, right V=max, left V=min, left H=center; C1+Photo.
FRAME = bytes.fromhex('5520047b060aeb34800601050004009406006c0100000400000400000400c7b9')


class DumlTests(unittest.TestCase):
    def test_fragmentation_noise_and_concatenation(self):
        stream = Stream()
        self.assertEqual(stream.feed(b'noise' + FRAME[:7]), [])
        self.assertEqual(stream.feed(FRAME[7:] + FRAME), [FRAME, FRAME])

    def test_bad_crc_and_header_are_rejected_and_resynchronized(self):
        for index in (3, 15, 31):
            bad = bytearray(FRAME)
            bad[index] ^= 1
            self.assertEqual(Stream().feed(bytes(bad) + FRAME), [FRAME])

    def test_incomplete_false_header_does_not_block_real_packet(self):
        fake = b'\x55\xff\x07\x00'
        self.assertEqual(Stream().feed(fake + FRAME), [FRAME])

    def test_stick_mapping_extrema_and_buttons(self):
        r = parse_sticks(FRAME)
        self.assertEqual((r.lx, r.ly, r.rx, r.ry), (0, -32768, 0, 32767))
        self.assertEqual(r.buttons, 0x1100)  # LB + A

    def test_wrong_command_and_invalid_crc_are_not_sticks(self):
        self.assertIsNone(parse_sticks(packet(0x24, b'\x01')))
        bad = bytearray(FRAME)
        bad[-1] ^= 1
        self.assertIsNone(parse_sticks(bytes(bad)))

    def test_request_length_and_header(self):
        request = packet(1)
        self.assertEqual(request[:4], bytes.fromhex('550d0433'))
        self.assertEqual(Stream().feed(request), [request])


if __name__ == '__main__':
    unittest.main()
