import unittest
from dataclasses import replace

from gasfix.core import Report, Settings, Throttle, normalize, axis_value


class ThrottleTests(unittest.TestCase):
    def ready(self, settings=None, level=0):
        t = Throttle(settings or Settings(), level)
        t.update(Report(), 0, True)
        return t

    def test_full_range_has_same_speed_at_different_rates(self):
        for rate in (20, 60, 125, 250):
            t = self.ready()
            for i in range(1, rate + 1):
                t.update(Report(ly=32767), i / rate, True)
            self.assertAlmostEqual(t.level, 1)

    def test_half_range_in_half_second_then_holds(self):
        t = self.ready(level=.5)
        for i in range(1, 51):
            t.update(Report(ly=32767), i / 100, True)
        self.assertEqual(t.level, 1)
        t.update(Report(), .51, True)
        self.assertEqual(t.level, 1)

    def test_clamps_and_inverts(self):
        t = self.ready(Settings(invert=True), .05)
        t.update(Report(ly=32767), .1, True)
        self.assertEqual(t.level, 0)
        for i in range(2, 15):
            t.update(Report(ly=-32768), i / 10, True)
        self.assertEqual(t.level, 1)

    def test_proportional_speed_and_deadzone(self):
        t = self.ready(level=.5)
        t.update(Report(ly=1000), .1, True)
        self.assertEqual(t.level, .5)
        t.update(Report(ly=17203), .2, True)  # approximately .525 -> half speed
        self.assertAlmostEqual(t.level, .55, places=4)

    def test_near_stop_threshold_is_inclusive(self):
        t = self.ready(Settings(mode='edge', threshold=.5), .5)
        t.update(Report(ly=16383), .1, True)
        self.assertEqual(t.level, .5)
        t.update(Report(ly=16384), .2, True)
        self.assertAlmostEqual(t.level, .6)
        t.update(Report(ly=-16384), .3, True)
        self.assertAlmostEqual(t.level, .5)

    def test_replaces_only_selected_axis(self):
        for name in ('lx', 'ly', 'rx', 'ry'):
            t = self.ready(Settings(axis=name), .75)
            report = Report(123, -456, 789, -1000, 12, 244, 0xB10F)
            out = t.update(report, .01, True)
            for field in ('lx', 'ly', 'rx', 'ry', 'lt', 'rt', 'buttons'):
                if field != name:
                    self.assertEqual(getattr(out, field), getattr(report, field))
            self.assertNotEqual(getattr(out, name), getattr(report, name))

    def test_disconnect_resets_and_requires_center(self):
        t = self.ready(level=.8)
        out = t.update(None, .1, True)
        self.assertEqual(out.ly, -32768)
        self.assertEqual(t.level, 0)
        t.update(Report(ly=32767), .11, True)
        self.assertEqual(t.level, 0)
        t.update(Report(), .12, True)
        t.update(Report(ly=32767), .22, True)
        self.assertAlmostEqual(t.level, .1)

    def test_disconnect_hold_releases_other_controls(self):
        t = self.ready(Settings(on_loss='hold'), .7)
        t.update(Report(lx=30000, buttons=0x1000), .1, True)
        out = t.update(None, .2, True)
        self.assertAlmostEqual(t.level, .7)
        self.assertEqual((out.lx, out.buttons), (0, 0))
        self.assertEqual(out.ly, axis_value(.7))

    def test_sleep_does_not_integrate_missed_time(self):
        t = self.ready(Settings(on_loss='hold'), .3)
        t.update(Report(ly=32767), 10, True)
        self.assertEqual(t.level, .3)
        t.update(Report(ly=32767), 10.01, True)
        self.assertEqual(t.level, .3)

    def test_start_hold_is_not_a_loss_before_first_connection(self):
        t = Throttle(Settings(on_start='hold', on_loss='zero'), .7)
        t.update(None, 0, True)
        t.update(None, 2, True)
        self.assertEqual(t.level, .7)
        t.update(Report(), 2.01, True)
        t.update(None, 2.02, True)
        self.assertEqual(t.level, 0)

    def test_disabled_passes_every_field_without_changing_level(self):
        t = self.ready(level=.7)
        report = Report(123, 234, 345, 456, 13, 17, 0xA)
        self.assertEqual(t.update(report, .1, False), report)
        self.assertEqual(t.level, .7)

    def test_normalize_endpoints(self):
        self.assertEqual(normalize(-32768), -1)
        self.assertEqual(normalize(32767), 1)
        self.assertEqual(axis_value(0), -32768)
        self.assertEqual(axis_value(.5), 0)
        self.assertEqual(axis_value(1), 32767)

    def test_rejects_invalid_settings(self):
        for options in ({'speed': float('nan')}, {'speed': 0}, {'deadzone': .95},
                        {'axis': 'lt'}, {'mode': 'unknown'}, {'threshold': 1.1}):
            with self.assertRaises(ValueError):
                Settings(**options).validate()


if __name__ == '__main__':
    unittest.main()
