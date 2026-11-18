"""Run the window or explicit hardware diagnostics."""
import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path


def diagnostics(mode):
    if mode == 'probe':
        from gasfix.dji import DjiSource
        source = DjiSource()
        try:
            reports = [source.read() for _ in range(30)]
            good = [r for r in reports if r is not None]
            if not good:
                raise RuntimeError('Нет корректных ответов стиков')
            return {'valid_reports': len(good), 'last': asdict(good[-1]), 'frame': source.last_raw}
        finally:
            source.close()
    if mode == 'output':
        from gasfix.core import Report
        from gasfix.windows import Output, XInput
        output = Output()
        try:
            index = output.user_index()
            if index is None:
                raise RuntimeError('Не определён XInput номер выхода')
            sample = Report(12345, -23456, 30001, -30002, 7, 231, 0xB10F)
            output.send(sample)
            time.sleep(.1)
            actual = XInput().read(index)
            if actual != sample:
                raise RuntimeError(f'Виртуальный выход отличается: {actual}')
            return {'exact_match': True, 'output_index': index, 'report': asdict(actual)}
        finally:
            output.close()
    if mode == 'integration':
        from gasfix.core import Settings
        from gasfix.engine import Engine
        from gasfix.windows import XInput
        engine = Engine(Settings(), 0)
        try:
            engine.start()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                time.sleep(.1)
                state = engine.snapshot()
                if state['connected']:
                    actual = XInput().read(state['output_index'])
                    if actual is not None and asdict(actual) == state['report']:
                        return {'connected': True, 'state': state, 'windows_report': asdict(actual)}
            raise RuntimeError(f'Сквозная проверка не пройдена: {engine.snapshot()}')
        finally:
            engine.stop()


def main():
    parser = argparse.ArgumentParser(description='VirtualGasFixer')
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--self-test-output', action='store_true')
    parser.add_argument('--integration-test', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--settings', type=Path)
    args = parser.parse_args()
    mode = 'probe' if args.probe else 'output' if args.self_test_output else 'integration' if args.integration_test else None
    if mode:
        try:
            result = {'ok': True, 'test': mode, **diagnostics(mode)}
            code = 0
        except Exception as error:
            result = {'ok': False, 'test': mode, 'error': str(error)}
            code = 1
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding='utf-8')
        if sys.stdout:
            print(text)
        return code
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gasfix.ui import App
    from gasfix.windows import bind
    import ctypes as c
    app = QApplication(sys.argv[:1])
    kernel = c.WinDLL('kernel32.dll', use_last_error=True)
    create = bind(kernel, 'CreateMutexW', [c.c_void_p, c.c_bool, c.c_wchar_p], c.c_void_p)
    close = bind(kernel, 'CloseHandle', [c.c_void_p], c.c_bool)
    # Keep the instance ID stable so an older installed version is also detected.
    mutex = create(None, False, 'Local\\DJIVirtualGasFixer')
    if not mutex:
        raise OSError(c.get_last_error(), 'Cannot create instance mutex')
    try:
        if c.get_last_error() == 183:
            QMessageBox.information(None, 'VirtualGasFixer', 'Программа уже запущена. Найди её окно на панели задач.')
            return 0
        window = App(args.settings)
        window.show()
        return app.exec()
    finally:
        close(mutex)


if __name__ == '__main__':
    sys.exit(main())
