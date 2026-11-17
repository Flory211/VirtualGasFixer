"""Input routing and one worker thread; UI never touches USB handles."""
import threading
import time
from dataclasses import asdict, replace

from .core import Report, Settings, Throttle, normalize, axis_value


class InputGuard:
    def __init__(self, selected, own, slots, generation):
        if own is None or selected == own or selected not in slots:
            raise RuntimeError('Выбранный Xbox недоступен или является собственным выходом. Выбери исходный контроллер.')
        self.selected, self.own, self.slots, self.generation = selected, own, tuple(slots), generation

    def check(self, own, slots, generation):
        if own != self.own or tuple(slots) != self.slots or generation != self.generation:
            raise RuntimeError('Состав устройств изменился. Отключи выход, проверь номер источника и подключись снова.')

    @classmethod
    def capture(cls, selected, output, xinput, watcher):
        generation = watcher.generation
        guard = cls(selected, output.user_index(), xinput.connected(), generation)
        guard.check(output.user_index(), xinput.connected(), watcher.generation)
        return guard

    def read(self, xinput, output, watcher):
        self.check(output.user_index(), xinput.connected(), watcher.generation)
        report = xinput.read(self.selected)
        self.check(output.user_index(), xinput.connected(), watcher.generation)
        return report


class Routing:
    def __init__(self, settings, level):
        self.throttle = Throttle(settings, level)
        self.latest = None
        self.received_at = None

    def step(self, report, now, enabled, fault=False):
        if fault:
            self.latest, self.received_at = None, None
        elif report is not None:
            self.latest, self.received_at = report, now
        current = self.latest if self.received_at is not None and now - self.received_at <= .25 else None
        return self.throttle.update(current, now, enabled)


class Engine:
    def __init__(self, settings, level):
        self.settings = settings.validate()
        self.routing = Routing(settings, level)
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.enabled = True
        self.zero_requested = False
        self.thread = None
        self.state = dict(running=False, connected=False, level=level, input=0, armed=False,
                          enabled=True, status='Выход отключён', output_index=None, report=asdict(Report()))

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Выход уже запущен')
        self.thread = threading.Thread(target=self._run, name='ControllerWorker', daemon=True)
        self.thread.start()

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = enabled

    def zero(self):
        with self.lock:
            self.zero_requested = True

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                raise RuntimeError('Поток ещё освобождает USB. Подожди завершения.')

    def _publish(self, **changes):
        with self.lock:
            self.state.update(changes)

    def _run(self):
        from .dji import DjiSource
        from .windows import DeviceWatcher, Output, XInput
        output = source = watcher = None
        status = 'Подключение…'
        blocked = False
        retry_at = 0
        try:
            self._publish(running=True, status=status)
            initial = replace(Report(), **{self.settings.axis: axis_value(self.routing.throttle.level)})
            output = Output(initial, self.settings.axis)
            xinput = XInput()
            own = output.user_index()
            self._publish(output_index=own)
            if self.settings.source == 'xbox':
                watcher = DeviceWatcher()
                guard = InputGuard.capture(self.settings.xbox_index, output, xinput, watcher)
            while not self.stop_event.is_set():
                now = time.perf_counter()
                report = None
                fault = blocked
                if not blocked:
                    try:
                        if self.settings.source == 'dji':
                            if source is None and now >= retry_at:
                                source = DjiSource()
                            if source:
                                report = source.read()
                        else:
                            report = guard.read(xinput, output, watcher)
                            if report is None:
                                raise RuntimeError('Xbox отключён. Проверь источник и подключись снова.')
                    except Exception as error:
                        status = str(error)
                        fault = True
                        if source:
                            try:
                                source.close()
                            except Exception:
                                pass
                            source = None
                        if self.settings.source == 'xbox':
                            blocked = True
                        retry_at = time.perf_counter() + 2
                with self.lock:
                    enabled = self.enabled
                    zero = self.zero_requested
                    self.zero_requested = False
                if zero:
                    self.routing.throttle.level = 0
                    self.routing.throttle.armed = False
                now = time.perf_counter()
                outgoing = self.routing.step(report, now, enabled, fault=fault)
                output.send(outgoing)
                connected = self.routing.throttle.connected
                if connected:
                    status = ('Обработка включена' if enabled else 'Прямая передача оси')
                    if enabled and not self.routing.throttle.armed:
                        status = 'Верни выбранный стик в центр'
                elif report is None and not fault and source is not None:
                    status = 'Нет свежих данных пульта'
                self._publish(connected=connected, level=self.routing.throttle.level,
                              input=normalize(getattr(self.routing.latest or Report(), self.settings.axis)),
                              armed=self.routing.throttle.armed, enabled=enabled, status=status, report=asdict(outgoing))
                self.stop_event.wait(.005)
        except Exception as error:
            status = str(error)
        finally:
            for resource in (source, watcher, output):
                if resource:
                    try:
                        resource.close()
                    except Exception as error:
                        status += f'; освобождение: {error}'
            self._publish(running=False, connected=False, level=self.routing.throttle.level,
                          status='Выход отключён' if self.stop_event.is_set() else status)
