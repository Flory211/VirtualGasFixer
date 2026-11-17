"""Small Windows API bindings; no driver installers."""
import ctypes as c
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

from .core import Report


class Gamepad(c.Structure):
    _fields_ = [('buttons', c.c_ushort), ('lt', c.c_ubyte), ('rt', c.c_ubyte),
                ('lx', c.c_short), ('ly', c.c_short), ('rx', c.c_short), ('ry', c.c_short)]


class State(c.Structure):
    _fields_ = [('packet', c.c_uint32), ('gamepad', Gamepad)]


def bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes = args
    function.restype = result
    return function


class XInput:
    def __init__(self):
        try:
            self.dll = c.WinDLL('xinput1_4.dll')
        except OSError:
            self.dll = c.WinDLL('xinput9_1_0.dll')
        self.get_state = bind(self.dll, 'XInputGetState', [c.c_uint32, c.POINTER(State)], c.c_uint32)

    def read(self, index):
        state = State()
        if self.get_state(index, c.byref(state)) != 0:
            return None
        gamepad = state.gamepad
        return Report(**{name: getattr(gamepad, name) for name in Report.__dataclass_fields__})

    def connected(self):
        return tuple(i for i in range(4) if self.read(i) is not None)


class Output:
    def __init__(self, initial=Report(ly=-32768), throttle_axis='ly'):
        self.client = None
        self.target = None
        self.attached = False
        self.registered = False
        self.notified_index = None
        self.index_ready = threading.Event()
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
        self.dll = c.CDLL(str(base / 'vendor' / 'ViGEmClient.dll'))
        self.alloc = bind(self.dll, 'vigem_alloc', [], c.c_void_p)
        self.connect = bind(self.dll, 'vigem_connect', [c.c_void_p], c.c_uint32)
        self.disconnect = bind(self.dll, 'vigem_disconnect', [c.c_void_p], None)
        self.free = bind(self.dll, 'vigem_free', [c.c_void_p], None)
        self.target_alloc = bind(self.dll, 'vigem_target_x360_alloc', [], c.c_void_p)
        self.target_add = bind(self.dll, 'vigem_target_add', [c.c_void_p, c.c_void_p], c.c_uint32)
        self.target_remove = bind(self.dll, 'vigem_target_remove', [c.c_void_p, c.c_void_p], c.c_uint32)
        self.target_free = bind(self.dll, 'vigem_target_free', [c.c_void_p], None)
        self.update = bind(self.dll, 'vigem_target_x360_update', [c.c_void_p, c.c_void_p, Gamepad], c.c_uint32)
        callback_type = c.WINFUNCTYPE(None, c.c_void_p, c.c_void_p, c.c_ubyte, c.c_ubyte, c.c_ubyte, c.c_void_p)
        def notification(client, target, large, small, index, context):
            self.notified_index = index if index < 4 else None
            self.index_ready.set()
        self.notification = callback_type(notification)
        self.register = bind(self.dll, 'vigem_target_x360_register_notification',
                             [c.c_void_p, c.c_void_p, callback_type, c.c_void_p], c.c_uint32)
        self.unregister = bind(self.dll, 'vigem_target_x360_unregister_notification', [c.c_void_p], None)
        try:
            self.client = self.alloc()
            if not self.client:
                raise RuntimeError('Не удалось создать клиент ViGEm')
            self.check(self.connect(self.client))
            self.target = self.target_alloc()
            if not self.target:
                raise RuntimeError('Не удалось создать виртуальный Xbox')
            self.check(self.target_add(self.client, self.target))
            self.attached = True
            self.send(initial)
            self.check(self.register(self.client, self.target, self.notification, None))
            self.registered = True
            self.index_ready.wait(.75)
            # LED assignment precedes the final PnP interface-arrival events.
            # Wait for enumeration before the engine captures its topology guard.
            time.sleep(.5)
            if initial == Report():
                # This ViGEmBus keeps its non-neutral startup sample until a
                # changed report arrives. One count on the throttle axis primes
                # that cache; all other channels remain exactly neutral.
                self.send(replace(initial, **{throttle_axis: 1}))
            self.send(initial)
        except Exception:
            self.close()
            raise

    @staticmethod
    def check(result):
        if result != 0x20000000:
            raise RuntimeError(f'ViGEm: ошибка 0x{result:08X}. Проверь установленный ViGEmBus.')

    def send(self, report):
        gamepad = Gamepad(**{name: getattr(report, name) for name, _ in Gamepad._fields_})
        self.check(self.update(self.client, self.target, gamepad))

    def user_index(self):
        # get_user_index() returned 0 for every device on this machine.
        # ViGEm notifications supply the real zero-based LED/player number.
        return self.notified_index

    def close(self):
        if self.target:
            if self.registered:
                self.unregister(self.target)
                self.registered = False
            if self.attached:
                self.target_remove(self.client, self.target)
            self.target_free(self.target)
            self.target = None
            self.attached = False
        if self.client:
            self.disconnect(self.client)
            self.free(self.client)
            self.client = None


class NotificationPayload(c.Union):
    _fields_ = [('bytes', c.c_byte * 400), ('alignment', c.c_void_p)]


class NotificationFilter(c.Structure):
    _fields_ = [('size', c.c_uint32), ('flags', c.c_uint32), ('kind', c.c_uint32),
                ('reserved', c.c_uint32), ('payload', NotificationPayload)]


class DeviceWatcher:
    """Increment generation on PnP interface changes, even with reused XInput slots."""
    def __init__(self):
        self.generation = 0
        self.handle = c.c_void_p()
        self.dll = c.WinDLL('cfgmgr32.dll')
        callback_type = c.WINFUNCTYPE(c.c_uint32, c.c_void_p, c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32)
        def changed(handle, context, action, event, length):
            self.generation += 1
            return 0
        self.callback = callback_type(changed)
        register = bind(self.dll, 'CM_Register_Notification',
                        [c.POINTER(NotificationFilter), c.c_void_p, callback_type, c.POINTER(c.c_void_p)], c.c_uint32)
        self.unregister = bind(self.dll, 'CM_Unregister_Notification', [c.c_void_p], c.c_uint32)
        config = NotificationFilter(size=c.sizeof(NotificationFilter), flags=1, kind=0)
        result = register(c.byref(config), None, self.callback, c.byref(self.handle))
        if result:
            raise RuntimeError(f'Не удалось включить защиту от смены устройств: {result}')

    def close(self):
        if self.handle:
            self.unregister(self.handle)
            self.handle = c.c_void_p()
