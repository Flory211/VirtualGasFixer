# PyInstaller build configuration.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ['main.py'], pathex=[],
    binaries=[('vendor/ViGEmClient.dll', 'vendor')] + collect_dynamic_libs('libusb_package'),
    datas=[('licenses', 'licenses')] + collect_data_files('libusb_package'),
    hiddenimports=['usb.backend.libusb1'], hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
# Qt 6.12 uses Windows' system ICU (unversioned exports). Dependency scanning
# found the unrelated ICU 78 DLL on the build host's PATH; bundling that DLL
# caused QtWidgets to fail with ERROR_PROC_NOT_FOUND. Use the OS DLL instead.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() != 'icuuc.dll'
              and not Path(entry[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DJIVirtualGasFixer',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DJIVirtualGasFixer')
