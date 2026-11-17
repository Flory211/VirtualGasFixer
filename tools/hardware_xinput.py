"""Windows integration check using a synthetic Xbox source, not a physical pad."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gasfix.core import Report, Settings
from gasfix.engine import Engine
from gasfix.windows import Output, XInput


def wait_for(predicate, timeout=3):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = predicate()
        if result:
            return result
        time.sleep(.01)
    raise AssertionError('Timed out')


source = Output(Report())
engine = None
try:
    index = source.user_index()
    assert index is not None
    source.send(Report())
    assert XInput().read(index) == Report(), 'Initial neutral report was not published by ViGEm'
    engine = Engine(Settings(source='xbox', xbox_index=index, on_loss='hold'), .2)
    engine.start()
    try:
        wait_for(lambda: engine.snapshot()['connected'] and engine.snapshot()['armed'])
    except AssertionError:
        print(engine.snapshot())
        raise
    sample = Report(12345, 32767, 23456, -12345, 19, 231, 0xB10F)
    source.send(sample)
    wait_for(lambda: engine.snapshot()['level'] >= .65)
    source.send(Report(12345, 0, 23456, -12345, 19, 231, 0xB10F))
    time.sleep(.1)
    held = engine.snapshot()['level']
    time.sleep(.15)
    state = engine.snapshot()
    assert abs(state['level'] - held) < .001
    actual = XInput().read(state['output_index'])
    assert actual is not None
    assert (actual.lx, actual.rx, actual.ry, actual.lt, actual.rt, actual.buttons) == (12345, 23456, -12345, 19, 231, 0xB10F)
    source.close()
    wait_for(lambda: not engine.snapshot()['connected'])
    time.sleep(.1)
    after_loss = engine.snapshot()
    assert abs(after_loss['level'] - held) < .001
    actual = XInput().read(after_loss['output_index'])
    assert (actual.lx, actual.rx, actual.ry, actual.lt, actual.rt, actual.buttons) == (0, 0, 0, 0, 0, 0)
    result = dict(ok=True, synthetic_source_index=index, output_index=state['output_index'],
                  held_level=held, exact_passthrough=True, loss_released_buttons=True, loss_held_throttle=True,
                  stopped_after_device_change=not after_loss['connected'])
    path = Path(__file__).resolve().parents[1] / 'docs' / 'xinput-hardware.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
finally:
    if engine:
        engine.stop()
    source.close()
