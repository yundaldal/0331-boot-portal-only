# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 업무포털 자동 로그인 프로그램 빌드 설정 (onedir 방식)
실행: pyinstaller autologin.spec
결과: dist/자동로그인/자동로그인.exe
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ksign_ref.png', '.'),                   # KSign 참조 이미지
        ('neis_ref.png', '.'),                    # 나이스 버튼 참조 이미지
        ('edufine_ref.png', '.'),                 # K-에듀파인 버튼 참조 이미지
    ],
    hiddenimports=[
        # pywinauto
        'pywinauto',
        'pywinauto.application',
        'pywinauto.keyboard',
        'pywinauto.mouse',
        'pywinauto.win32_hooks',
        'pywinauto.uia_element_info',
        'pywinauto.controls.uia_controls',
        'pywinauto.controls.win32_controls',
        'comtypes',
        'comtypes.client',
        'comtypes.automation',
        # pyautogui / PIL
        'pyautogui',
        'PIL',
        'PIL.Image',
        'PIL.ImageGrab',
        'pyscreeze',
        # selenium (Chrome + Edge)
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.edge.webdriver',
        'selenium.webdriver.edge.options',
        'selenium.webdriver.edge.service',
        'webdriver_manager',
        'webdriver_manager.chrome',
        'webdriver_manager.microsoft',
        # win32
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'win32clipboard',
        'pywintypes',
        'win32com',
        'win32com.client',
        'win32com.shell',
        # 기타
        'configparser',
        'tkinter',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.ttk',
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
    name='자동로그인',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='자동로그인',
)
