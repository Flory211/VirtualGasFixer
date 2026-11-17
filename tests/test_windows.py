import ctypes as c
import unittest
from unittest.mock import patch

from gasfix.core import Report, axis_value
from gasfix.windows import Output


class Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class ClientDll:
    def __init__(self):
        self.sent = []
        self.unregistered = False
        for name in ('vigem_connect', 'vigem_target_add', 'vigem_target_remove'):
            setattr(self, name, Function(lambda *args: 0x20000000))
        for name in ('vigem_disconnect', 'vigem_free', 'vigem_target_free'):
            setattr(self, name, Function(lambda *args: None))
        self.vigem_alloc = Function(lambda: 1)
        self.vigem_target_x360_alloc = Function(lambda: 2)
        self.vigem_target_x360_update = Function(self.send)
        self.vigem_target_x360_get_user_index = Function(self.wrong_index)
        self.vigem_target_x360_register_notification = Function(self.register)
        self.vigem_target_x360_unregister_notification = Function(self.unregister)

    def send(self, client, target, gamepad):
        self.sent.append(Report(**{name: getattr(gamepad, name) for name in Report.__dataclass_fields__}))
        return 0x20000000

    def wrong_index(self, client, target, index):
        c.cast(index, c.POINTER(c.c_uint32))[0] = 0  # actual observed driver bug
        return 0x20000000

    def register(self, client, target, callback, context):
        callback(client, target, 0, 0, 1, context)  # actual source of reliable index
        return 0x20000000

    def unregister(self, target):
        self.unregistered = True


class OutputTests(unittest.TestCase):
    def test_first_report_uses_selected_axis_and_restored_level(self):
        dll = ClientDll()
        initial = Report(rx=axis_value(.7))
        with patch('gasfix.windows.c.CDLL', return_value=dll), patch('gasfix.windows.time.sleep'):
            output = Output(initial)
            self.assertEqual(dll.sent[0], initial)
            output.close()

    def test_notification_identifies_second_pad_despite_broken_index_api(self):
        dll = ClientDll()
        with patch('gasfix.windows.c.CDLL', return_value=dll), patch('gasfix.windows.time.sleep'):
            output = Output()
            self.assertEqual(output.user_index(), 1)
            output.close()
            self.assertTrue(dll.unregistered)


if __name__ == '__main__':
    unittest.main()
