"""Direct RM330 USB transport. Never imports/starts the installed emulator."""
import time

import libusb_package
import usb.core
import usb.util

from .duml import Stream, packet, parse_sticks


class DjiSource:
    def __init__(self):
        self.device = None
        self.interface = None
        self.claimed = False
        self.stream = Stream()
        self.last_raw = None
        backend = libusb_package.get_libusb1_backend()
        if backend is None:
            raise RuntimeError('Не найдена собственная libusb программы')
        self.device = usb.core.find(idVendor=0x2CA3, idProduct=0x1023, backend=backend)
        if self.device is None:
            raise RuntimeError('DJI RC RM330 не найден. Включи пульт и подключи нижний USB-C порт.')
        try:
            config = self.device[0]
            self.interface = next((i for i in config if i.bInterfaceClass == 0xFF and i.bInterfaceSubClass == 0x43), None)
            if self.interface is None:
                raise RuntimeError('Не найден USB-интерфейс DUML')
            self.ep_in = next((e for e in self.interface if e.bmAttributes & 3 == 2 and e.bEndpointAddress & 0x80), None)
            self.ep_out = next((e for e in self.interface if e.bmAttributes & 3 == 2 and not e.bEndpointAddress & 0x80), None)
            if self.ep_in is None or self.ep_out is None:
                raise RuntimeError('Не найдены USB-каналы DUML')
            usb.util.claim_interface(self.device, self.interface.bInterfaceNumber)
            self.claimed = True
            self.ep_out.write(packet(0x24, b'\x01'), timeout=200)
        except Exception:
            self.close()
            raise

    def read(self):
        self.ep_out.write(packet(1), timeout=100)
        try:
            data = bytes(self.ep_in.read(4096, timeout=35))
        except usb.core.USBTimeoutError:
            return None
        result = None
        for frame in self.stream.feed(data):
            report = parse_sticks(frame)
            if report is not None:
                self.last_raw = frame.hex()
                result = report
        return result

    def close(self):
        if self.device is not None:
            try:
                if self.claimed:
                    usb.util.release_interface(self.device, self.interface.bInterfaceNumber)
            finally:
                usb.util.dispose_resources(self.device)
                self.device = None
                self.claimed = False
