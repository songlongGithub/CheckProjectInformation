# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置文件

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        'pandas',
        'openpyxl',
        'requests',
        'fuzzywuzzy',
        'Levenshtein',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='体检方案智能核对工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/MedicalExamChecker.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='体检方案智能核对工具',
)

# macOS 应用包配置
app = BUNDLE(
    coll,
    name='体检方案智能核对工具.app',
    icon='resources/icons/MedicalExamChecker.icns',
    bundle_identifier='com.mycompany.medicalexamchecker',
    version='2.3.0',
)
