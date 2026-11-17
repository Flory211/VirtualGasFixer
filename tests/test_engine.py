import unittest
from types import SimpleNamespace

from gasfix.core import Report, Settings
from gasfix.engine import InputGuard, Routing


class GuardTests(unittest.TestCase):
    def test_own_output_and_unknown_index_are_never_input(self):
        for own in (None, 1):
            with self.assertRaises(RuntimeError):
                InputGuard(1, own, (1, 2), 0)

    def test_slot_reassignment_and_device_event_latch_stop(self):
        guard = InputGuard(1, 2, (1, 2), 7)
        guard.check(2, (1, 2), 7)
        for args in ((1, (1, 2), 7), (2, (1, 2, 3), 7), (2, (1, 2), 8)):
            with self.assertRaises(RuntimeError):
                guard.check(*args)

    def test_change_during_read_discards_the_report(self):
        guard = InputGuard(1, 2, (1, 2), 7)
        watcher = SimpleNamespace(generation=7)
        output = SimpleNamespace(user_index=lambda: 2)
        def changed_read(index):
            watcher.generation += 1
            return Report(buttons=0x1000)
        source = SimpleNamespace(connected=lambda: (1, 2), read=changed_read)
        with self.assertRaises(RuntimeError):
            guard.read(source, output, watcher)


class RoutingTests(unittest.TestCase):
    def test_invalid_packets_do_not_extend_freshness(self):
        r = Routing(Settings(), .8)
        r.step(Report(), 0, True)
        r.step(Report(ly=32767), .1, True)
        r.step(None, .2, True)
        out = r.step(None, .36, True)
        self.assertEqual(out.ly, -32768)
        self.assertEqual(r.throttle.level, 0)

    def test_input_fault_immediately_neutralizes_and_holds(self):
        r = Routing(Settings(on_loss='hold'), .7)
        r.step(Report(lx=30000, buttons=0x1000), 0, False)
        out = r.step(None, .01, False, fault=True)
        self.assertEqual((out.lx, out.buttons), (0, 0))
        self.assertAlmostEqual(r.throttle.level, .7)


if __name__ == '__main__':
    unittest.main()
