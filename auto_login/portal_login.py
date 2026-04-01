"""
교육청 업무포털 자동 로그인 모듈.
Chrome 또는 Edge를 열고 인증서 로그인 버튼 클릭 후
KSign 인증서 창을 cert_window_handler 로 처리.
"""

import logging
import os
import re
import sys
import time

import cert_window_handler

logger = logging.getLogger('AutoLogin')

# pyautogui 화면 모서리 이동 시 FailSafeException 방지
try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pass

# ── 브라우저 프로파일 ─────────────────────────────────────────────────
BROWSER_PROFILES = {
    'chrome': {
        'exe_paths': [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ],
        'process_name': 'chrome.exe',
        'user_data_dir': os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data"),
        'display_name': 'Chrome',
    },
    'edge': {
        'exe_paths': [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\msedge.exe"),
        ],
        'process_name': 'msedge.exe',
        'user_data_dir': os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data"),
        'display_name': 'Edge',
    },
}

# 인증서 로그인 버튼 셀렉터 후보 (우선순위 순)
CERT_BTN_SELECTORS = [
    ('css',   '#btnLgn'),                   # 전 지역 공통 버튼 ID (최우선)
    ('xpath', "//*[@id='btnLgn']"),          # ID XPath 폴백
    ('xpath', "//*[contains(text(), '교육행정 전자서명 인증서 로그인')]"),
    ('xpath', "//*[contains(text(), '전자서명 인증서 로그인')]"),
    ('xpath', "//*[contains(text(), '인증서 로그인')]"),
    ('xpath', "//*[contains(text(), '전자서명 인증서')]"),
    ('css',   "a.btn-cert, button.btn-cert"),
    ('css',   "input[type='button'][value*='인증서'], input[type='submit'][value*='인증서']"),
    ('xpath', "//a[contains(@onclick,'cert') or contains(@href,'cert')]"),
]


def _get_profile(settings):
    """settings에서 브라우저 프로파일을 반환."""
    browser = settings.get('browser', 'chrome')
    return BROWSER_PROFILES.get(browser, BROWSER_PROFILES['chrome'])


def _find_browser_exe(profile):
    """브라우저 실행 파일 경로 탐색."""
    return next((p for p in profile['exe_paths'] if os.path.exists(p)), None)


def _wait_browser_exit(profile, timeout=5):
    """브라우저 프로세스가 완전히 종료될 때까지 0.1초 단위 폴링."""
    import subprocess as _sp
    proc = profile['process_name']
    deadline = time.time() + timeout
    _NO_WIN = _sp.CREATE_NO_WINDOW
    while time.time() < deadline:
        result = _sp.run(['tasklist', '/fi', f'IMAGENAME eq {proc}'],
                         capture_output=True, text=True, creationflags=_NO_WIN)
        if proc not in result.stdout:
            return
        time.sleep(0.1)
    _sp.run(['taskkill', '/f', '/im', proc], capture_output=True,
            creationflags=_NO_WIN)
    time.sleep(0.3)


def _close_browser(profile):
    """브라우저 프로세스를 종료하고 프로파일 잠금 파일을 삭제한다."""
    import subprocess
    proc = profile['process_name']
    name = profile['display_name']
    result = subprocess.run(['taskkill', '/f', '/im', proc], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode == 0:
        logger.info(f"기존 {name} 프로세스 종료 완료")
    else:
        logger.debug(f"종료할 {name} 프로세스 없음")

    user_data = profile['user_data_dir']
    for lock_file in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
        target = os.path.join(user_data, lock_file)
        if os.path.exists(target):
            try:
                os.remove(target)
                logger.debug(f"{name} 잠금 파일 삭제: {lock_file}")
            except Exception:
                pass
    _wait_browser_exit(profile, timeout=5)


def prepare_browser(portal_url, settings):
    """
    브라우저 사전 준비.
    기존 브라우저 종료 → 포털 URL로 브라우저 실행 → 창 대기.
    """
    import subprocess as _sp

    profile = _get_profile(settings)
    name = profile['display_name']
    browser_exe = _find_browser_exe(profile)
    if not browser_exe:
        logger.error(f"{name} 실행 파일을 찾을 수 없습니다 (prepare_browser).")
        return False

    user_data_dir = profile['user_data_dir']

    _sp.run(['taskkill', '/f', '/im', profile['process_name']], capture_output=True,
            creationflags=_sp.CREATE_NO_WINDOW)
    _wait_browser_exit(profile, timeout=5)

    for lock in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
        lpath = os.path.join(user_data_dir, lock)
        if os.path.exists(lpath):
            try:
                os.remove(lpath)
            except Exception:
                pass
    _suppress_restore_dialog(user_data_dir)

    browser_args = [
        browser_exe,
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-infobars',
        f'--user-data-dir={user_data_dir}',
        '--profile-directory=Default',
        portal_url,
    ]
    # 실행 전 기존 Electron/브라우저 창 핸들 저장 (오인 방지)
    existing_hwnds = set()
    try:
        from pywinauto import Desktop as _Desktop
        existing_hwnds = {w.handle for w in _Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1")}
    except Exception:
        pass
    logger.info(f"{name} 사전 실행 시작")
    import subprocess
    subprocess.Popen(browser_args)
    _wait_for_browser_window(timeout=30, existing_hwnds=existing_hwnds)
    _handle_permission_popup(timeout=5)
    logger.info(f"{name} 사전 준비 완료")
    return True


def login(settings, advanced, chrome_ready=False):
    """
    업무포털 자동 로그인 수행.

    Args:
        chrome_ready: True이면 브라우저가 이미 준비된 상태 → launch 단계 생략.

    Returns:
        True  : 로그인 성공
        False : 실패
    """
    profile = _get_profile(settings)
    name = profile['display_name']
    password = settings['cert_password']
    portal_url = settings.get('portal_url', 'https://gen.eduptl.kr/bpm_lgn_lg00_001.do')

    logger.info(f"── 업무포털 로그인 단계 시작 ({name}) ──")

    try:
        result = _login_via_existing_browser(portal_url, password, profile,
                                             skip_launch=chrome_ready)
        if result:
            # 로그인 성공 여부 실제 검증 (btnLgn 소멸 확인)
            verified = _verify_login_success(timeout=20)
            if verified:
                logger.info("업무포털 로그인 성공 (검증 완료)")
                return True
            logger.warning("로그인 검증 실패 (btnLgn 지속) → Selenium fallback 시도")

        # 기존 방식 실패 시: 재시작 + Selenium fallback
        logger.warning(f"기존 {name} 방식 실패 → {name} 재시작 + Selenium fallback 시도")
        _close_browser(profile)
        time.sleep(5)

        return _login_via_selenium(portal_url, password, profile)

    except Exception as e:
        logger.error(f"업무포털 로그인 중 예외 발생: {e}", exc_info=True)
        return False


def _login_via_selenium(portal_url, password, profile):
    """Selenium WebDriver를 사용한 폴백 로그인."""
    name = profile['display_name']
    browser_key = 'edge' if profile['process_name'] == 'msedge.exe' else 'chrome'

    if browser_key == 'edge':
        from selenium import webdriver
        from selenium.webdriver.edge.service import Service
        from selenium.webdriver.edge.options import Options
        from webdriver_manager.microsoft import EdgeChromiumDriverManager

        user_data_dir = profile['user_data_dir']
        logger.info(f"{name} 브라우저 실행 중 (Selenium + 사용자 프로파일)...")
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        if os.path.isdir(user_data_dir):
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument("--profile-directory=Default")
        service = Service(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
    else:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        user_data_dir = profile['user_data_dir']
        logger.info(f"{name} 브라우저 실행 중 (Selenium + 사용자 프로파일)...")
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        if os.path.isdir(user_data_dir):
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument("--profile-directory=Default")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

    logger.info(f"{name} 실행 완료")
    logger.info(f"업무포털 접속: {portal_url}")
    driver.get(portal_url)

    time.sleep(3)
    _handle_permission_popup()

    btn = _find_and_click_cert_button(driver)
    if btn is None:
        logger.error("인증서 로그인 버튼을 찾을 수 없습니다. 페이지 소스를 확인하세요.")
        return False

    logger.info("인증서 로그인 버튼 클릭 완료 → KSign 창 대기")

    success = cert_window_handler.wait_and_handle_cert_window(
        password=password,
        timeout=90,
        poll_interval=0.5,
    )

    if success:
        logger.info("업무포털 로그인 성공 (브라우저는 열린 상태 유지)")
        return True
    else:
        logger.error("업무포털 인증서 처리 실패")
        return False


def _suppress_restore_dialog(user_data_dir):
    """
    브라우저 강제 종료 후 재시작 시 나타나는 '페이지를 복원하시겠습니까?' 다이얼로그 억제.
    Preferences 파일의 exit_type을 Normal로 설정한다. (Chrome/Edge 공통 Chromium 구조)
    """
    import json
    prefs_path = os.path.join(user_data_dir, 'Default', 'Preferences')
    if not os.path.exists(prefs_path):
        return
    try:
        with open(prefs_path, 'r', encoding='utf-8') as f:
            prefs = json.load(f)
        p = prefs.setdefault('profile', {})
        p['exit_type'] = 'Normal'
        p['exited_cleanly'] = True
        with open(prefs_path, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, ensure_ascii=False, separators=(',', ':'))
        logger.debug("복원 다이얼로그 억제: exit_type=Normal 설정 완료")
    except Exception as e:
        logger.debug(f"Preferences 수정 실패 (무시): {e}")


def _handle_permission_popup(timeout=8):
    """
    브라우저 권한 팝업("허용/차단")을 pywinauto로 탐색하여 '허용' 클릭.
    Chrome/Edge 모두 Chrome_WidgetWin_1 클래스 사용.
    """
    from pywinauto import Desktop
    import time as t

    logger.info("브라우저 권한 팝업 확인 중...")
    start = t.time()

    while t.time() - start < timeout:
        try:
            desk = Desktop(backend="uia")
            for win in desk.windows(class_name="Chrome_WidgetWin_1"):
                try:
                    for btn in win.descendants(control_type="Button"):
                        label = btn.window_text().strip()
                        if label in ("허용", "Allow", "열기", "Open"):
                            btn.click()
                            logger.info(f"권한 팝업 → '{label}' 클릭")
                            t.sleep(0.5)
                            return True
                except Exception:
                    pass
        except Exception:
            pass
        t.sleep(1)

    logger.debug("권한 팝업 없음 (또는 이미 처리됨)")
    return False


def _find_and_click_cert_button(driver):
    """
    다중 셀렉터 전략으로 인증서 로그인 버튼을 탐색하고 클릭.
    일반 click → JS click 순으로 폴백.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    wait = WebDriverWait(driver, 5)

    try:
        WebDriverWait(driver, 20).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "isloading-overlay"))
        )
        logger.info("로딩 오버레이 사라짐 → 버튼 탐색 시작")
    except Exception:
        logger.debug("오버레이 없거나 대기 타임아웃 → 버튼 탐색 진행")

    by_map = {
        'xpath': By.XPATH,
        'css':   By.CSS_SELECTOR,
        'id':    By.ID,
    }

    for sel_type, selector in CERT_BTN_SELECTORS:
        try:
            by = by_map.get(sel_type, By.XPATH)
            element = wait.until(EC.presence_of_element_located((by, selector)))
            logger.info(f"버튼 발견 (type={sel_type}, selector={selector!r})")

            try:
                element.click()
                logger.info("버튼 클릭 완료 (일반 click)")
                return element
            except Exception as e1:
                logger.debug(f"일반 click 실패: {e1}")

            try:
                driver.execute_script("arguments[0].click();", element)
                logger.info("버튼 클릭 완료 (JS click)")
                return element
            except Exception as e2:
                logger.debug(f"JS click 실패: {e2}")

        except (TimeoutException, NoSuchElementException):
            continue
        except Exception as e:
            logger.debug(f"셀렉터 시도 중 예외 ({selector!r}): {e}")
            continue

    return None


# ── subprocess + pywinauto 방식 (WebDriver 없이 브라우저 직접 실행) ─────────


def _login_via_existing_browser(portal_url, password, profile, skip_launch=False):
    """
    pyautogui 방식: 브라우저를 자동화 플래그 없이 실행하고 화면에서 인증서 버튼을 찾아 클릭.
    - nProtect가 WebDriver/CDP 플래그를 감지할 수 없음
    - 사용자 프로파일 사용 → NPKI/CrossEx 확장 활성화
    """
    import subprocess, time
    import pyautogui
    import ctypes

    name = profile['display_name']

    if skip_launch:
        logger.info(f"{name} 사전 준비됨 → 인증서 버튼 탐색으로 바로 진행")
        time.sleep(0.2)
    else:
        browser_exe = _find_browser_exe(profile)
        if not browser_exe:
            logger.error(f"{name} 실행 파일을 찾을 수 없습니다.")
            return False

        user_data_dir = profile['user_data_dir']

        import subprocess as _sp
        _sp.run(['taskkill', '/f', '/im', profile['process_name']], capture_output=True,
                creationflags=_sp.CREATE_NO_WINDOW)
        _wait_browser_exit(profile, timeout=5)
        for lock in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
            lpath = os.path.join(user_data_dir, lock)
            if os.path.exists(lpath):
                try:
                    os.remove(lpath)
                except Exception:
                    pass
        _suppress_restore_dialog(user_data_dir)

        browser_args = [
            browser_exe,
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-infobars',
            f'--user-data-dir={user_data_dir}',
            '--profile-directory=Default',
            portal_url,
        ]
        existing_hwnds = set()
        try:
            from pywinauto import Desktop as _Desktop
            existing_hwnds = {w.handle for w in _Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1")}
        except Exception:
            pass
        logger.info(f"{name} 실행 (pyautogui 방식, 자동화 플래그 없음)")
        subprocess.Popen(browser_args)

        _wait_for_browser_window(timeout=20, existing_hwnds=existing_hwnds)
        _handle_permission_popup(timeout=5)
        time.sleep(1)

    # DPI 배율 보정 (Windows 고DPI 환경)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    # 브라우저 창을 최상위로 올리기 (다른 프로그램이 가리는 경우 대응)
    _bring_browser_to_front()

    # 인증서 버튼 탐색: UIA ID 기반 (최대 20초, 0.5초 간격)
    btn_pos = None
    logger.info("UIA로 인증서 버튼 탐색 중 (btnLgn ID → 텍스트 폴백)...")
    for attempt in range(40):
        btn_pos = _find_cert_btn_via_uia()
        if btn_pos:
            break
        if attempt % 10 == 9:
            logger.debug(f"UIA 버튼 탐색 {attempt+1}/40 실패, 계속 재시도")
        time.sleep(0.5)

    if btn_pos is None:
        logger.error("인증서 버튼을 찾을 수 없습니다 (pyautogui 방식).")
        return False

    x, y = int(btn_pos[0]), int(btn_pos[1])
    logger.info(f"인증서 버튼 클릭: ({x}, {y})")
    pyautogui.FAILSAFE = False
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.1)
    pyautogui.click()

    time.sleep(0.5)
    for _ in range(3):
        cert_window_handler._dismiss_blocking_popups()
        time.sleep(0.2)

    return _portal_keyboard_cert_flow(password, timeout=90)


def _bring_browser_to_front():
    """
    브라우저 창을 최상위로 올린다.
    메신저 등 다른 프로그램이 브라우저를 가리고 있을 때 호출.
    Chrome/Edge 모두 Chrome_WidgetWin_1 클래스 사용.
    """
    import win32gui, win32con
    try:
        from pywinauto import Desktop
        for win in Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1"):
            if win.is_visible() and win.window_text().strip():
                hwnd = win.handle
                # 최소화 상태면 복원
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)
                win32gui.SetForegroundWindow(hwnd)
                logger.info(f"브라우저 창 최상위로 올림: '{win.window_text()}'")
                time.sleep(0.3)
                return
    except Exception as e:
        logger.debug(f"브라우저 포커스 설정 실패 (무시): {e}")


def _wait_for_browser_window(timeout=20, existing_hwnds=None):
    """
    브라우저 창(페이지 로드 완료)이 나타날 때까지 폴링 대기.
    Chrome/Edge 모두 Chrome_WidgetWin_1 클래스 사용.
    """
    from pywinauto import Desktop
    start = time.time()
    while time.time() - start < timeout:
        try:
            desk = Desktop(backend="uia")
            wins = [w for w in desk.windows(class_name="Chrome_WidgetWin_1")
                    if w.is_visible() and w.window_text().strip()]
            if existing_hwnds is not None:
                wins = [w for w in wins if w.handle not in existing_hwnds]
            if wins:
                logger.info(f"브라우저 창 감지 ({time.time()-start:.1f}초): '{wins[0].window_text()}'")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    logger.warning("브라우저 창 대기 타임아웃")
    return False


def _find_cert_btn_via_uia(left_edge=False):
    """
    브라우저 UIA 트리에서 인증서 버튼 텍스트를 탐색하여 화면 좌표 반환.
    Chrome/Edge 모두 Chrome_WidgetWin_1 클래스 사용.
    """
    from pywinauto import Desktop
    CERT_TEXTS = ['교육행정 전자서명 인증서 로그인', '전자서명 인증서 로그인', '인증서 로그인']

    def _pick_x(rect):
        return rect.left + 15 if left_edge else rect.right - 15

    try:
        desk = Desktop(backend='uia')
        for win in desk.windows(class_name='Chrome_WidgetWin_1'):
            if not win.is_visible():
                continue
            # 1순위: AutomationId "btnLgn"으로 직접 탐색
            try:
                elems = win.descendants(auto_id='btnLgn')
                if elems:
                    rect = elems[0].rectangle()
                    cx = _pick_x(rect)
                    cy = (rect.top + rect.bottom) // 2
                    logger.info(f"UIA 버튼 발견 (AutomationId=btnLgn): ({cx}, {cy})")
                    return (cx, cy)
            except Exception:
                pass
            # 2순위: 버튼 텍스트로 탐색
            for text in CERT_TEXTS:
                try:
                    elems = win.descendants(title=text)
                    if elems:
                        rect = elems[0].rectangle()
                        cx = _pick_x(rect)
                        cy = (rect.top + rect.bottom) // 2
                        side = '왼쪽' if left_edge else '우측'
                        logger.info(f"UIA 버튼 발견: '{text}' at {side} 모서리 ({cx}, {cy})")
                        return (cx, cy)
                except Exception:
                    pass
            # 3순위: 부분 텍스트 매칭
            try:
                for elem in win.descendants():
                    try:
                        t = elem.window_text()
                        if '인증서' in t and '로그인' in t and len(t) < 60:
                            rect = elem.rectangle()
                            cx = _pick_x(rect)
                            cy = (rect.top + rect.bottom) // 2
                            side = '왼쪽' if left_edge else '우측'
                            logger.info(f"UIA 부분 매칭: '{t}' at {side} 모서리 ({cx}, {cy})")
                            return (cx, cy)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"UIA 탐색 오류: {e}")
    return None


def _portal_keyboard_cert_flow(password, timeout=90):
    """
    포털 KSign 오버레이 암호 입력: Tab → 클립보드 암호 붙여넣기 → Enter.
    2.5초마다 재시도. timeout 초 내 성공 여부 반환.
    """
    import pyautogui
    import win32clipboard
    import win32gui

    deadline = time.time() + timeout
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        try:
            cert_window_handler._dismiss_blocking_popups()
        except Exception:
            pass

        logger.info(f"포털 인증서 암호 입력 시도 #{attempt} (Tab → 클립보드 → Enter)")
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(password)
            win32clipboard.CloseClipboard()

            # 브라우저 창에 포커스 복구 (Chrome/Edge 공통 클래스)
            try:
                hwnd = win32gui.FindWindow('Chrome_WidgetWin_1', None)
                if hwnd:
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.3)
            except Exception:
                pass

            pyautogui.press('tab')
            time.sleep(0.4)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.3)
            pyautogui.press('enter')
            logger.info("포털 인증서 암호 입력 완료 (Enter 전송)")
            time.sleep(2.5)
            return True
        except Exception as e:
            logger.warning(f"포털 키보드 입력 시도 #{attempt} 실패: {e}")
            time.sleep(2.5)

    logger.error("포털 인증서 암호 입력 타임아웃")
    return False


# ── 로그인 성공 검증 ──────────────────────────────────────────────────────────


def _verify_login_success(timeout=20):
    """
    업무포털 로그인 성공 확인.
    인증서 버튼(btnLgn)이 사라지면 페이지가 로그인 후 화면으로 전환된 것.
    반환: True(성공 확인) / False(타임아웃)
    """
    from pywinauto import Desktop
    start = time.time()
    while time.time() - start < timeout:
        found_login_btn = False
        try:
            for win in Desktop(backend='uia').windows(class_name='Chrome_WidgetWin_1'):
                if not win.is_visible():
                    continue
                try:
                    if win.descendants(auto_id='btnLgn'):
                        found_login_btn = True
                        break
                except Exception:
                    pass
        except Exception:
            pass

        if not found_login_btn:
            logger.info(f"로그인 성공 확인: btnLgn 소멸 (경과 {time.time()-start:.1f}초)")
            return True
        time.sleep(0.5)

    logger.warning(f"로그인 성공 확인 타임아웃 ({timeout}초): btnLgn 아직 존재")
    return False


# ── 로그인 후 추가 서비스 열기 ───────────────────────────────────────────────


def _extract_region(portal_url):
    """portal_url에서 지역 코드 추출. 예: https://gen.eduptl.kr/... → 'gen'"""
    m = re.match(r'https?://(\w+)\.eduptl\.kr', portal_url or '')
    return m.group(1) if m else None


def _get_ref_image(filename):
    """빌드/개발 환경 모두에서 참조 이미지(PIL Image) 로드."""
    from PIL import Image
    dirs = ([os.path.dirname(sys.executable), sys._MEIPASS]
            if getattr(sys, 'frozen', False)
            else [os.path.dirname(os.path.abspath(__file__))])
    for d in dirs:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            try:
                return Image.open(p).copy()
            except Exception:
                pass
    return None


def _dismiss_portal_banners():
    """
    포털 로그인 직후 표시되는 배너/공지 팝업을 닫는다.
    '닫기', '확인', '오늘 하루 열지 않기' 등 버튼을 탐색하여 클릭.
    """
    CLOSE_LABELS = ('닫기', '확인', '오늘 하루 열지 않기', 'Close',
                    '×', 'X', '오늘하루열지않기')
    try:
        from pywinauto import Desktop
        desk = Desktop(backend='uia')
        for win in desk.windows(class_name='Chrome_WidgetWin_1'):
            if not win.is_visible():
                continue
            try:
                for btn in win.descendants(control_type='Button'):
                    label = btn.window_text().strip()
                    if label in CLOSE_LABELS:
                        try:
                            btn.click()
                            logger.info(f"포털 배너 닫기: '{label}' 클릭")
                            time.sleep(0.4)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass


def _click_service_button_by_image(service):
    """
    참조 이미지(neis_ref.png / edufine_ref.png)로 버튼을 찾아 Ctrl+클릭.
    Ctrl+클릭 → 새 탭에서 열기 (현재 포털 탭 유지).
    반환: True(성공) / False(실패)
    """
    import pyautogui

    ref_file = 'neis_ref.png' if service == 'neis' else 'edufine_ref.png'
    ref_img = _get_ref_image(ref_file)
    if ref_img is None:
        logger.warning(f"참조 이미지 없음: {ref_file}")
        return False

    for confidence in (0.85, 0.75, 0.65):
        try:
            box = cert_window_handler.locate_on_all_screens(ref_img, confidence=confidence)
            if box:
                cx = box.left + box.width // 2
                cy = box.top + box.height // 2
                logger.info(f"이미지 매칭 성공 ({service}, conf={confidence}): ({cx},{cy})")
                pyautogui.FAILSAFE = False
                pyautogui.moveTo(cx, cy, duration=0.3)
                time.sleep(0.15)
                pyautogui.keyDown('ctrl')
                pyautogui.click(cx, cy)
                pyautogui.keyUp('ctrl')
                logger.info(f"{service} 버튼 Ctrl+클릭 완료 (새 탭)")
                return True
        except Exception as e:
            logger.debug(f"이미지 매칭 예외 ({service}, conf={confidence}): {e}")

    logger.debug(f"이미지 매칭 실패: {service}")
    return False


def _find_service_btn_via_uia(service, region):
    """
    UIA Hyperlink(AutomationId = URL)에서 서비스 버튼 좌표를 탐색.
    Chrome: neis→klef URL, Edge: neis→neis URL (브라우저별 ID 패턴 역전 허용).
    반환: (cx, cy) or None
    """
    # 두 브라우저 모두 대응: 지역 코드 기반 URL 패턴
    if service == 'neis':
        patterns = [f'{region}.neis.go.kr', 'neis.go.kr'] if region else ['neis.go.kr']
    else:  # edufine
        patterns = [f'klef.{region}.go.kr', 'klef.'] if region else ['klef.']

    try:
        from pywinauto import Desktop
        desk = Desktop(backend='uia')
        for win in desk.windows(class_name='Chrome_WidgetWin_1'):
            if not win.is_visible():
                continue
            try:
                # Hyperlink 타입만 스캔 (전체 descendants 대비 빠름)
                for elem in win.descendants(control_type='Hyperlink'):
                    try:
                        aid = elem.automation_id()
                        if aid and any(p in aid for p in patterns):
                            rect = elem.rectangle()
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            logger.info(
                                f"UIA 서비스 버튼 발견 ({service}): "
                                f"id={aid[:70]!r} pos=({cx},{cy})"
                            )
                            return (cx, cy)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"UIA 서비스 버튼 탐색 오류: {e}")
    return None


def _click_service_by_text(service):
    """
    UIA 텍스트 기반으로 서비스 버튼 탐색 후 Ctrl+클릭 (최종 폴백).
    반환: True / False
    """
    import pyautogui

    keywords = (['나이스', 'NEIS'] if service == 'neis'
                else ['에듀파인', 'K-에듀파인', 'k-에듀파인'])

    try:
        from pywinauto import Desktop
        for win in Desktop(backend='uia').windows(class_name='Chrome_WidgetWin_1'):
            if not win.is_visible():
                continue
            try:
                for elem in win.descendants():
                    try:
                        text = elem.window_text().strip()
                        if not text:
                            continue
                        if any(kw.lower() in text.lower() for kw in keywords):
                            rect = elem.rectangle()
                            w_px = rect.right - rect.left
                            h_px = rect.bottom - rect.top
                            # 너무 크거나 좌표 0인 요소 제외 (컨테이너 오인식 방지)
                            if w_px > 300 or h_px > 100 or (rect.left == 0 and rect.top == 0):
                                continue
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            logger.info(
                                f"텍스트 매칭 ({service}): '{text}' at ({cx},{cy})"
                            )
                            pyautogui.FAILSAFE = False
                            pyautogui.moveTo(cx, cy, duration=0.3)
                            time.sleep(0.1)
                            pyautogui.keyDown('ctrl')
                            pyautogui.click(cx, cy)
                            pyautogui.keyUp('ctrl')
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"텍스트 매칭 오류: {e}")
    return False


def open_additional_services(settings):
    """
    업무포털 로그인 성공 후 나이스/에듀파인을 새 탭으로 열기.

    after_login 값:
        'none'    → 업무포털만 (아무것도 안 함)
        'neis'    → 나이스만
        'edufine' → K-에듀파인만
        'both'    → 나이스 + K-에듀파인

    버튼 탐색 우선순위:
        1순위: 이미지 매칭 (neis_ref.png / edufine_ref.png)
        2순위: UIA Hyperlink AutomationId (지역코드 포함 URL 패턴)
        3순위: UIA 텍스트 매칭 ('나이스' / '에듀파인')

    Ctrl+클릭으로 새 탭에서 열어 포털 탭을 유지.
    브라우저(Chrome/Edge) 공통 — Chrome_WidgetWin_1 클래스 사용.
    """
    after_login = settings.get('after_login', 'none')
    if after_login == 'none':
        return

    portal_url = settings.get('portal_url', '')
    region = _extract_region(portal_url)
    logger.info(f"추가 서비스 열기 시작 (after_login={after_login}, region={region})")

    # ── 배너/팝업 먼저 닫기 ──────────────────────────────────────────
    _dismiss_portal_banners()
    time.sleep(1.0)

    # 브라우저 창을 최상위로 (배너 클릭 후 포커스 잃을 수 있음)
    _bring_browser_to_front()
    time.sleep(0.5)

    services = []
    if after_login in ('neis', 'both'):
        services.append('neis')
    if after_login in ('edufine', 'both'):
        services.append('edufine')

    for service in services:
        label = '나이스' if service == 'neis' else 'K-에듀파인'
        logger.info(f"[{label}] 버튼 탐색 시작")

        ok = False

        # 1순위: 이미지 매칭
        ok = _click_service_button_by_image(service)

        if not ok:
            # 2순위: UIA AutomationId (URL 패턴)
            pos = _find_service_btn_via_uia(service, region)
            if pos:
                import pyautogui
                cx, cy = pos
                pyautogui.FAILSAFE = False
                pyautogui.moveTo(cx, cy, duration=0.3)
                time.sleep(0.15)
                pyautogui.keyDown('ctrl')
                pyautogui.click(cx, cy)
                pyautogui.keyUp('ctrl')
                logger.info(f"[{label}] UIA 버튼 Ctrl+클릭 완료")
                ok = True

        if not ok:
            # 3순위: UIA 텍스트 매칭
            ok = _click_service_by_text(service)

        if ok:
            logger.info(f"[{label}] 열기 완료 → 새 탭 대기")
            time.sleep(2.0)  # 새 탭 로딩 대기
        else:
            logger.warning(f"[{label}] 버튼을 찾지 못했습니다 (이미지/UIA/텍스트 모두 실패)")
