"""Controller reports and time-based throttle; no platform dependencies."""
import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Report:
    lx: int = 0
    ly: int = 0
    rx: int = 0
    ry: int = 0
    lt: int = 0
    rt: int = 0
    buttons: int = 0


@dataclass(frozen=True)
class Settings:
    source: str = 'dji'
    xbox_index: int = 0
    axis: str = 'ly'
    invert: bool = False
    mode: str = 'proportional'
    speed: float = 100.0
    deadzone: float = .05
    threshold: float = .90
    on_start: str = 'zero'
    on_loss: str = 'zero'

    def validate(self):
        if self.source not in ('dji', 'xbox') or self.axis not in ('lx', 'ly', 'rx', 'ry'):
            raise ValueError('Неверный источник или ось')
        if type(self.xbox_index) is not int or not 0 <= self.xbox_index <= 3:
            raise ValueError('Номер Xbox должен быть от 1 до 4')
        if type(self.invert) is not bool or self.mode not in ('proportional', 'edge'):
            raise ValueError('Неверная инверсия или режим')
        for value in (self.speed, self.deadzone, self.threshold):
            if type(value) not in (float, int) or not -10000 < value < 10000 or not math.isfinite(value):
                raise ValueError('Настройки должны быть конечными числами')
        if not 0 < self.speed <= 1000 or not 0 <= self.deadzone < self.threshold <= 1:
            raise ValueError('Скорость: 0–1000 %/с; зона центра должна быть меньше порога')
        if self.on_start not in ('zero', 'hold') or self.on_loss not in ('zero', 'hold'):
            raise ValueError('Неверная политика сохранения газа')
        return self


def normalize(value):
    return max(-1.0, min(1.0, value / (32768 if value < 0 else 32767)))


def axis_value(level):
    return round((level * 2 - 1) * (32768 if level < .5 else 32767))


class Throttle:
    stale_after = .25

    def __init__(self, settings, level=0):
        self.settings = settings.validate()
        self.level = max(0.0, min(1.0, level))
        self.last_time = None
        self.connected = False
        self.armed = False
        self.was_enabled = False

    def update(self, report, now, enabled):
        dt = 0 if self.last_time is None else now - self.last_time
        self.last_time = now
        if dt < 0 or dt > self.stale_after:
            if self.connected and self.settings.on_loss == 'zero':
                self.level = 0
            self.connected = False
            self.armed = False
            dt = 0
        if report is None:
            if self.connected and self.settings.on_loss == 'zero':
                self.level = 0
            self.connected = False
            self.armed = False
            self.was_enabled = enabled
            return replace(Report(), **{self.settings.axis: axis_value(self.level)})
        if not self.connected or enabled != self.was_enabled:
            self.armed = False
            dt = 0
        self.connected = True
        self.was_enabled = enabled
        x = normalize(getattr(report, self.settings.axis))
        if self.settings.invert:
            x = -x
        if abs(x) <= self.settings.deadzone:
            self.armed = True
        if not enabled:
            return report
        direction = 0.0
        if self.armed:
            if self.settings.mode == 'edge':
                direction = (1 if x >= self.settings.threshold else
                             -1 if x <= -self.settings.threshold else 0)
            elif abs(x) > self.settings.deadzone:
                direction = math.copysign((abs(x) - self.settings.deadzone) /
                                          (1 - self.settings.deadzone), x)
        self.level = max(0.0, min(1.0, self.level + self.settings.speed / 100 * direction * dt))
        return replace(report, **{self.settings.axis: axis_value(self.level)})
