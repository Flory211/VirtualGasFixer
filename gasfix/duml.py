"""DUML wire format, adapted from deviverr/DJI-RC-Emulator (MIT).

See licenses/DJI-RC-Emulator.txt. Unlike the reference, validates both
checksums and retains partial packets across bulk reads.
"""
import struct

from .core import Report, axis_value


def crc(data, seed, polynomial):
    value = seed
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (polynomial if value & 1 else 0)
    return value


def valid(frame):
    return (len(frame) >= 13 and frame[0] == 0x55
            and frame[2] & 0xFC == 4
            and ((frame[2] & 3) << 8 | frame[1]) == len(frame)
            and crc(frame[:3], 0x77, 0x8C) == frame[3]
            and crc(frame[:-2], 0x3692, 0x8408) == int.from_bytes(frame[-2:], 'little'))


def packet(command, payload=b''):
    length = 13 + len(payload)
    if length > 1023:
        raise ValueError('DUML packet too long')
    header = bytes([0x55, length & 255, 4 | (length >> 8)])
    body = header + bytes([crc(header, 0x77, 0x8C)])
    body += bytes.fromhex('0a06eb344006') + bytes([command]) + payload
    return body + struct.pack('<H', crc(body, 0x3692, 0x8408))


class Stream:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            start = self.buffer.find(0x55)
            if start < 0:
                self.buffer.clear()
                break
            del self.buffer[:start]
            if len(self.buffer) < 4:
                break
            length = self.buffer[1] | (self.buffer[2] & 3) << 8
            if (self.buffer[2] & 0xFC != 4 or length < 13
                    or crc(self.buffer[:3], 0x77, 0x8C) != self.buffer[3]):
                del self.buffer[0]
                continue
            if len(self.buffer) < length:
                break
            candidate = bytes(self.buffer[:length])
            if valid(candidate):
                frames.append(candidate)
                del self.buffer[:length]
            else:
                del self.buffer[0]
        return frames


def parse_sticks(frame):
    if not valid(frame) or len(frame) not in (32, 38) or frame[9:11] != b'\x06\x01':
        return None
    # Responses travel RC -> application, not application -> RC.
    if frame[4:6] != b'\x06\x0a' or not frame[8] & 0x80:
        return None
    base = 12 if len(frame) == 32 else 13
    raw = [int.from_bytes(frame[i:i + 2], 'little') for i in range(base, base + 15, 3)]
    if any(not 0 <= value <= 2047 for value in raw):
        return None
    def stick(value):
        return axis_value(max(0, min(1, (value - 364) / 1320)))
    button_byte = frame[base - 1]
    buttons = 0
    for bit, mask in ((1, 0x100), (2, 0x200), (4, 0x1000), (8, 0x4000), (16, 0x20)):
        if button_byte & bit:
            buttons |= mask
    camera = (raw[4] - 1024) / 660
    if camera > .8:
        buttons |= 0x8000  # Y
    elif camera < -.8:
        buttons |= 0x2000  # B
    if base + 17 <= len(frame) - 2:
        scroll = (int.from_bytes(frame[base + 15:base + 17], 'little') - 1024) / 660
        if scroll > .8:
            buttons |= 1
        elif scroll < -.8:
            buttons |= 2
    return Report(lx=stick(raw[3]), ly=stick(raw[2]), rx=stick(raw[0]), ry=stick(raw[1]), buttons=buttons)
