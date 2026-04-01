"""
KSign 인증서 선택 창 감지 → 비밀번호 입력 → 확인 클릭 공통 모듈.

탐지 전략 (우선순위):
  1) pyautogui 이미지 매칭: 화면에서 KSign 창 이미지를 찾아 좌표 클릭
     → nProtect 보호 프로세스에도 작동 (화면 픽셀만 사용)
  2) pywinauto UIA/win32 폴백: 창 제목/구조 기반 탐색
"""

import logging
import os
import time

logger = logging.getLogger('AutoLogin')

# pyautogui 화면 모서리 이동 시 FailSafeException 방지
try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pass

import sys
import ctypes
from PIL import Image, ImageGrab

# ── 한글 경로 안전 이미지 로드 ──────────────────────────────────────────
# OpenCV imread()는 Windows에서 비ASCII(한글) 경로를 읽지 못한다.
# PIL Image 객체로 로드하면 pyautogui.locateOnScreen이 imread를 우회한다.
def load_image(path):
    """경로의 이미지를 PIL Image로 로드. 한글 경로에서도 동작."""
    if path and os.path.exists(path):
        try:
            return Image.open(path).copy()   # .copy()로 파일 핸들 즉시 해제
        except Exception as e:
            logger.debug(f"이미지 로드 실패 ({path}): {e}")
    return None


def locate_on_all_screens(needle_img, confidence=0.75, region=None, grayscale=False):
    """
    전체 모니터(보조 모니터 포함)에서 이미지를 탐색하여 Box를 반환.
    pyautogui.locateOnScreen은 주모니터만 캡처하므로 이 함수로 대체.
    반환 좌표는 가상 데스크톱 절대 좌표 (pyautogui.click에 바로 사용 가능).

    Args:
        region: (left, top, width, height) 절대 화면 좌표. 해당 영역만 탐색.
    """
    import pyautogui
    from pyscreeze import Box

    # 가상 데스크톱 원점 (보조 모니터가 왼쪽/위에 있으면 음수)
    vx = ctypes.windll.user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    vy = ctypes.windll.user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN

    screenshot = ImageGrab.grab(all_screens=True)

    try:
        if region:
            # region은 절대 좌표 → 스크린샷 좌표로 변환 후 크롭
            rx, ry = region[0] - vx, region[1] - vy
            crop_box = (rx, ry, rx + region[2], ry + region[3])
            cropped = screenshot.crop(crop_box)
            box = pyautogui.locate(needle_img, cropped,
                                   confidence=confidence, grayscale=grayscale)
            if box is None:
                return None
            return Box(left=box.left + region[0], top=box.top + region[1],
                       width=box.width, height=box.height)

        box = pyautogui.locate(needle_img, screenshot,
                               confidence=confidence, grayscale=grayscale)
        if box is None:
            return None
        return Box(left=box.left + vx, top=box.top + vy,
                   width=box.width, height=box.height)
    except Exception:
        return None

# KSign 참조 이미지 경로 탐색 (PyInstaller 빌드 호환)
if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS          # 번들 임시 폴더
    _EXE_DIR  = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _EXE_DIR  = _BASE_DIR

_KSIGN_REF_CANDIDATES = [
    os.path.join(_EXE_DIR,  'ksign_ref.png'),   # exe 옆 (사용자가 교체 가능)
    os.path.join(_BASE_DIR, 'ksign_ref.png'),   # 번들 내부
    os.path.join(_BASE_DIR, '인증서.png'),
    os.path.join(os.path.dirname(_BASE_DIR), '인증서.png'),
]
_KSIGN_REF_PATH = next((p for p in _KSIGN_REF_CANDIDATES if os.path.exists(p)), None)
KSIGN_REF_IMAGE = load_image(_KSIGN_REF_PATH)   # PIL Image 또는 None

# KSign 창 내 상대 좌표 (이미지 기준, 0~1 비율)
# ksign_ref.png 실제 픽셀 측정값 기반
_PWD_FIELD_REL  = (0.69, 0.843)  # 인증서 암호 입력 필드 중심
_CONFIRM_BTN_REL = (0.755, 0.952)  # 파란색 확인 버튼 중심

# KSign 창 제목 후보 (실제 환경에 따라 다를 수 있으므로 복수 지원)
CERT_WINDOW_TITLES = [
    '인증서 선택', '인증서선택', 'Certificate Selection',
    '교육기관 전자서명인증센터',   # KSign 실제 창 제목 (이미지 확인)
    '전자서명인증센터', 'KSign',
    '인증서 암호', '인증서암호',
]


def wait_and_handle_cert_window(password, timeout=120, poll_interval=2,
                                extra_titles=None, keyboard_mode=False):
    """
    인증서 선택 창이 나타날 때까지 폴링 대기 후 비밀번호 입력 & 확인 클릭.

    Args:
        password (str)        : config.ini에서 읽은 인증서 비밀번호
        timeout (int)         : 최대 대기 시간 (초)
        poll_interval (float) : 폴링 주기 (초)
        extra_titles (list)   : 추가로 탐색할 창 제목 목록
        keyboard_mode (bool)  : True = 포털용 (Tab+암호+Enter 키보드 방식만 사용)
                                False = 메신저용 (Win32 창 직접 탐지 + 클립보드)

    Returns:
        True  : 로그인 처리 완료
        False : 타임아웃 또는 처리 실패
    """
    from pywinauto import Desktop

    titles = CERT_WINDOW_TITLES[:]
    if extra_titles:
        titles.extend(extra_titles)

    mode_label = "키보드(포털)" if keyboard_mode else "Win32창(메신저)"
    logger.info(f"인증서 창 대기 시작 [{mode_label}] (최대 {timeout}초, 폴링 {poll_interval}초)")
    if KSIGN_REF_IMAGE:
        logger.info(f"KSign 참조 이미지: {KSIGN_REF_IMAGE}")
    else:
        logger.warning("ksign_ref.png 없음 → 이미지 매칭 비활성화")

    start = time.time()
    seen_windows = set()  # 처리된 창 hwnd 추적 (hwnd 기반 — 같은 제목 다른 인스턴스 구분)
    handled_cert_dialogs = set()  # 인증서 선택 완료된 창 핸들 추적
    _keyboard_next_attempt = 5.0   # 첫 키보드 시도: 폴링 시작 5초 후

    while time.time() - start < timeout:
        elapsed = time.time() - start

        # ── 0순위: 방해 팝업 자동 닫기 ──────────────────────────────────
        _click_chrome_allow_popup()
        _dismiss_blocking_popups()

        # ── 1순위: 화면 이미지 매칭 (nProtect 보호 창에도 작동) ──────────
        if KSIGN_REF_IMAGE:
            result = _try_ksign_via_image(password)
            if result:
                return True

        # ── 공통: 인증서 선택 다이얼로그 처리 (메신저+포털 모두) ──────────
        # ListView가 있는 창 = 인증서 목록 → 첫 번째 인증서 선택 후 확인 클릭
        _handle_cert_selection_dialog(handled_cert_dialogs)

        # ══ Win32 암호 입력 창 탐지 (메신저 + 포털 공통) ═════════════════
        # Edit + 확인 버튼이 있는 창 = 암호 입력 창 (ListView 없는 것만)
        SKIP_CLASSES = ('IME', 'MSCTFIME UI', 'Default IME', 'CiceroUIWndFrame',
                        'Shell_TrayWnd', 'Progman', 'WorkerW', 'Chrome_WidgetWin_1',
                        'tooltips_class32', 'SysShadow')
        CONFIRM_LABELS = ('확인', 'OK', '로그인', '인증')
        try:
            from pywinauto import Desktop as _Desktop
            _desk = _Desktop(backend="win32")
            for w in _desk.windows():
                try:
                    cn = w.class_name()
                    if cn in SKIP_CLASSES:
                        continue
                    hwnd = w.handle
                    if hwnd in seen_windows:
                        continue
                    t = w.window_text().strip()
                    if t:
                        logger.info(f"[새 창 감지] title={t!r}  class={cn!r}")
                    seen_windows.add(hwnd)

                    # Edit + 확인 버튼 조합 확인
                    edits = w.descendants(class_name="Edit") or w.descendants(control_type="Edit")
                    btns = ([b for b in w.descendants(class_name="Button")
                             if b.window_text().strip() in CONFIRM_LABELS] or
                            [b for b in w.descendants(control_type="Button")
                             if b.window_text().strip() in CONFIRM_LABELS])
                    if edits and btns:
                        logger.info(f"[즉시 처리] 암호 입력 창 후보: title={t!r} class={cn!r}")
                        time.sleep(0.3)
                        try:
                            w.set_focus()
                        except Exception:
                            pass
                        return _enter_password_and_confirm(w, password)
                except Exception:
                    pass
        except Exception:
            pass

        # ── 키보드 방식 폴백: Win32 탐지 실패 시 Tab+암호+Enter (2.5초 간격) ──
        if elapsed >= _keyboard_next_attempt:
            logger.info(f"[키보드 폴백] Tab + 암호 + Enter 시도 (경과 {elapsed:.1f}초)")
            _try_keyboard_tab_input(password)
            time.sleep(2.5)
            if not _is_ksign_win32_visible():
                logger.info("[키보드 폴백] KSign Win32 창 없음 → 완료로 간주")
                return True
            _keyboard_next_attempt = elapsed + 2.5

        time.sleep(poll_interval)

    # 타임아웃 후 휴리스틱 탐지: 제목 무관, Edit + 확인 버튼 조합으로 탐색
    logger.warning("제목 기반 탐색 실패 → 창 구조(Edit + 확인 버튼) 휴리스틱 탐색 시작")
    return _heuristic_find_cert_window(password, seen_windows)


# ── KSign 창 소멸 확인 ───────────────────────────────────────────


def _is_ksign_win32_visible():
    """Win32 KSign 창(인증서 관련 제목)이 현재 화면에 있는지 확인한다."""
    CERT_TITLE_KEYWORDS = ('인증서', 'ksign', 'crossex', 'npki', '전자서명', 'certificate')
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="win32").windows():
            try:
                t = w.window_text().strip().lower()
                if any(kw in t for kw in CERT_TITLE_KEYWORDS):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _is_ksign_gone():
    """KSign 창/이미지가 화면에서 사라졌는지 확인한다."""
    # 이미지 매칭으로 확인
    if KSIGN_REF_IMAGE:
        try:
            import pyautogui
            box = locate_on_all_screens(KSIGN_REF_IMAGE, confidence=0.55)
            if box:
                return False  # 아직 화면에 있음
        except Exception:
            pass

    # pywinauto로 KSign 창 제목 확인
    try:
        from pywinauto import Desktop
        desk = Desktop(backend="uia")
        for title in CERT_WINDOW_TITLES:
            if desk.windows(title=title):
                return False  # 아직 열려 있음
    except Exception:
        pass

    return True  # 창 없음 → 로그인 완료로 간주


# ── 비밀번호 입력 내부 함수들 ────────────────────────────────────


def _handle_cert_selection_dialog(handled_set):
    """
    인증서 선택 다이얼로그(SysListView32 포함)를 찾아
    첫 번째 인증서를 선택하고 확인 버튼을 클릭한다.
    메신저(인증서+암호 통합창)와 포털(인증서 선택 전용창) 모두 처리.
    """
    SKIP_CLASSES = ('Shell_TrayWnd', 'Progman', 'WorkerW', 'Chrome_WidgetWin_1',
                    'IME', 'MSCTFIME UI', 'Default IME', 'CiceroUIWndFrame',
                    'tooltips_class32', 'SysShadow')
    CONFIRM_LABELS = ('확인', 'OK')
    # 인증서 관련 창 제목 키워드 (대소문자 무시) — 무관한 앱(프린터 등) 오인식 방지
    CERT_TITLE_KEYWORDS = ('인증서', 'ksign', 'crossex', 'npki', '전자서명', 'certificate', 'sign')
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="win32").windows():
            try:
                cn = w.class_name()
                if cn in SKIP_CLASSES:
                    continue
                hwnd = w.handle
                if hwnd in handled_set:
                    continue
                listviews = w.descendants(class_name="SysListView32")
                if not listviews:
                    continue
                btns = [b for b in w.descendants(class_name="Button")
                        if b.window_text().strip() in CONFIRM_LABELS]
                if not btns:
                    continue
                t = w.window_text().strip()
                # 인증서 관련 창 제목인지 확인 (무관한 앱 오인식 방지)
                t_lower = t.lower()
                if not any(kw in t_lower for kw in CERT_TITLE_KEYWORDS):
                    logger.debug(f"[인증서 선택] 비인증서 창 무시: title={t!r}")
                    continue
                logger.info(f"[인증서 선택] 다이얼로그 감지: title={t!r} class={cn!r}")
                handled_set.add(hwnd)
                # 첫 번째 인증서 선택
                _select_first_cert(listviews[0])
                time.sleep(0.5)
                # 확인 클릭
                btns[0].click()
                logger.info("[인증서 선택] 첫 번째 인증서 선택 + 확인 클릭 완료")
                time.sleep(1.0)
                return
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"인증서 선택 처리 중 오류: {e}")


def _select_first_cert(listview):
    """ListView에서 첫 번째 인증서 항목을 선택한다."""
    try:
        listview.set_focus()
        time.sleep(0.2)
        try:
            listview.item(0).click()
            logger.info("인증서 목록: 첫 번째 항목 클릭")
        except Exception:
            # pywinauto 키보드로 첫 항목 이동 (글로벌 pyautogui 사용 안 함)
            try:
                listview.type_keys('{HOME}', pause=0.1)
                logger.info("인증서 목록: 키보드로 첫 번째 항목 선택")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"인증서 항목 선택 실패: {e}")


def _enter_password_and_confirm(window, password):
    """비밀번호 입력 필드를 찾아 입력하고 확인 버튼을 클릭한다."""
    # 창 내에 인증서 목록(ListView)이 있으면 먼저 선택 (메신저 통합 다이얼로그)
    try:
        listviews = window.descendants(class_name="SysListView32")
        if listviews:
            _select_first_cert(listviews[0])
            time.sleep(0.3)
    except Exception:
        pass

    pwd_field = _find_password_field(window)
    if pwd_field is None:
        logger.error("비밀번호 입력 필드를 찾을 수 없습니다.")
        return False

    # 클립보드를 1순위로 사용 (특수문자 암호도 정확히 입력됨)
    input_methods = [
        ('clipboard', _input_clipboard),
        ('send_keystrokes', _input_send_keystrokes),
        ('type_keys', _input_type_keys),
    ]

    success = False
    for name, func in input_methods:
        try:
            # 입력 필드를 직접 클릭하여 포커스 확보 (set_focus보다 확실)
            try:
                pwd_field.click_input()
            except Exception:
                pwd_field.set_focus()
            time.sleep(0.3)
            _clear_field(pwd_field)
            func(pwd_field, password)
            logger.info(f"비밀번호 입력 성공 (방식: {name})")
            success = True
            break
        except Exception as e:
            logger.warning(f"입력 방식 '{name}' 실패: {e}")

    if not success:
        logger.error("모든 비밀번호 입력 방식 실패")
        return False

    time.sleep(0.3)
    return _click_confirm(window, pwd_field)


def _heuristic_find_cert_window(password, exclude_titles=None):
    """
    창 제목과 무관하게 Edit 컨트롤 + '확인' 버튼 조합으로 인증서 창을 탐색.
    uia 백엔드 → win32 백엔드 순으로 탐색.
    """
    from pywinauto import Desktop
    SKIP_CLASSES = ('Shell_TrayWnd', 'Progman', 'WorkerW', 'Chrome_WidgetWin_1',
                    'tooltips_class32', 'SysShadow', 'IME', 'MSCTFIME UI')
    CONFIRM_LABELS = ('확인', 'OK', '로그인', '인증')

    for backend in ('uia', 'win32'):
      try:
        desk = Desktop(backend=backend)
        for w in desk.windows():
            try:
                title = w.window_text().strip()
                cls = w.class_name()
                # 시스템/배경 창 제외만 (seen_windows 제외 제거 — KSign 창도 재탐색)
                if cls in SKIP_CLASSES:
                    continue

                # win32 백엔드는 class_name, uia 백엔드는 control_type 사용
                if backend == 'win32':
                    edits = w.descendants(class_name="Edit")
                    buttons = [b for b in w.descendants(class_name="Button")
                               if b.window_text().strip() in CONFIRM_LABELS]
                else:
                    edits = w.descendants(control_type="Edit")
                    buttons = [b for b in w.descendants(control_type="Button")
                               if b.window_text().strip() in CONFIRM_LABELS]

                if not edits:
                    continue
                if not buttons:
                    continue

                logger.info(f"[휴리스틱] 인증서 창 후보 발견: title={title!r} class={cls!r}")
                time.sleep(0.5)
                try:
                    w.set_focus()
                except Exception:
                    pass
                return _enter_password_and_confirm(w, password)
            except Exception:
                continue
      except Exception as e:
        logger.error(f"휴리스틱 탐색 중 오류 (backend={backend}): {e}")

    logger.error("휴리스틱 탐색으로도 인증서 창을 찾지 못했습니다.")
    return False


def _find_password_field(window):
    """창 내부에서 비밀번호 Edit 컨트롤을 탐색한다."""
    # 방법 1: UIA Edit 타입
    try:
        edits = window.descendants(control_type="Edit")
        if edits:
            return edits[0]
    except Exception:
        pass

    # 방법 2: win32 edit 클래스
    try:
        from pywinauto import Desktop
        desk = Desktop(backend="win32")
        wins = desk.windows(title_re=".*인증서.*")
        if wins:
            edits = wins[0].descendants(class_name="Edit")
            if edits:
                return edits[0]
    except Exception:
        pass

    return None


def _clear_field(field):
    """입력 필드의 기존 내용을 지운다."""
    try:
        field.type_keys('^a{DELETE}', pause=0.05)
    except Exception:
        pass


def _input_type_keys(field, password):
    """방법 1: type_keys 가상 키 이벤트"""
    field.type_keys(password, with_spaces=True, pause=0.05)


def _input_send_keystrokes(field, password):
    """방법 2: send_keystrokes WM_CHAR 메시지 — pywinauto 특수문자 이스케이프 처리"""
    special = set('{}()[]~^+%')
    escaped = ''.join('{' + c + '}' if c in special else c for c in password)
    field.send_keystrokes(escaped)


def _input_clipboard(field, password):
    """방법 3: 클립보드 붙여넣기"""
    _set_clipboard(password)
    field.set_focus()
    time.sleep(0.2)
    from pywinauto.keyboard import send_keys
    send_keys('^v')  # Ctrl+V


def _set_clipboard(text):
    """Windows 클립보드에 텍스트를 설정한다."""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return
    except ImportError:
        pass

    # win32clipboard 없을 경우 tkinter 폴백
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    r.clipboard_clear()
    r.clipboard_append(text)
    r.update()
    r.after(500, r.destroy)
    r.mainloop()


def _click_confirm(window, pwd_field):
    """팝업 제거 후 Enter 키로 확인. 실패 시 '확인' 버튼 클릭으로 대체."""
    # 팝업이 있으면 먼저 제거
    try:
        _dismiss_blocking_popups()
    except Exception:
        pass

    # Enter 키 우선 (gen메신저 흐름: 비밀번호 입력 → Enter)
    try:
        pwd_field.type_keys('{ENTER}')
        logger.info("Enter 키로 확인 완료")
        return True
    except Exception as e:
        logger.warning(f"Enter 키 입력 실패: {e}")

    # Enter 실패 시 버튼 클릭 폴백
    confirm_labels = ('확인', 'OK', '로그인', '인증')
    try:
        btns = []
        try:
            btns = list(window.descendants(class_name="Button"))
        except Exception:
            pass
        if not btns:
            try:
                btns = list(window.descendants(control_type="Button"))
            except Exception:
                pass
        for btn in btns:
            if btn.window_text().strip() in confirm_labels:
                btn.click()
                logger.info(f"'{btn.window_text()}' 버튼 클릭 완료 (폴백)")
                return True
    except Exception as e:
        logger.warning(f"버튼 탐색 실패: {e}")

    logger.error("Enter 키 및 버튼 클릭 모두 실패")
    return False


# ── 이미지 매칭 기반 KSign 처리 ──────────────────────────────────────────────


def _dismiss_blocking_popups():
    """
    로그인 흐름을 방해하는 팝업을 감지해 확인/닫기 버튼을 자동 클릭한다.
    현재 대상:
      - '인증서 관리' 창: "인증서의 비밀번호를 입력 하십시오." 메시지 팝업
    """
    BLOCKING_TITLES = ('인증서 관리',)
    CONFIRM_LABELS = ('확인', 'OK', '닫기', 'Close')
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="win32").windows():
            try:
                t = w.window_text().strip()
                if t not in BLOCKING_TITLES:
                    continue
                btns = [b for b in w.descendants(class_name="Button")
                        if b.window_text().strip() in CONFIRM_LABELS]
                if btns:
                    btns[0].click()
                    logger.info(f"[방해 팝업 닫기] '{t}' → '{btns[0].window_text()}' 클릭")
            except Exception:
                pass
    except Exception:
        pass


def _click_chrome_allow_popup():
    """
    Chrome이 CrossEx/KSign 실행 전 띄우는 '앱 허용' 팝업을 클릭.
    '허용'/'Allow'/'열기' 버튼이 보이면 즉시 클릭한다.
    """
    from pywinauto import Desktop
    ALLOW_LABELS = ('허용', 'Allow', '열기', 'Open')
    try:
        desk = Desktop(backend='uia')
        for win in desk.windows(class_name='Chrome_WidgetWin_1'):
            try:
                for btn in win.descendants(control_type='Button'):
                    label = btn.window_text().strip()
                    if label in ALLOW_LABELS:
                        btn.click()
                        logger.info(f"Chrome 앱 허용 팝업 클릭: '{label}'")
                        return
            except Exception:
                pass
    except Exception:
        pass


def _try_ksign_via_image(password):
    """
    화면에서 KSign 창 이미지를 찾아 암호 입력 + 확인 클릭.
    pywinauto process access 없이 순수 화면 좌표 기반으로 동작.
    → nProtect 보호 프로세스에도 작동.
    """
    import pyautogui

    if not KSIGN_REF_IMAGE:
        return False

    try:
        box = locate_on_all_screens(KSIGN_REF_IMAGE, confidence=0.55)
        if box:
            logger.info(f"[이미지 매칭] KSign 창 발견: {box}")
        else:
            logger.debug("이미지 매칭: KSign 창 없음")
            return False
    except Exception as e:
        logger.debug(f"이미지 매칭 예외: {e}")
        return False

    left, top, width, height = box.left, box.top, box.width, box.height
    logger.info(f"[이미지 매칭] KSign 창 발견: left={left} top={top} w={width} h={height}")
    time.sleep(0.5)

    # 인증서 암호 입력 필드 클릭 (창 내 상대 좌표)
    pwd_x = left + int(width * _PWD_FIELD_REL[0])
    pwd_y = top  + int(height * _PWD_FIELD_REL[1])
    logger.info(f"암호 필드 클릭: ({pwd_x}, {pwd_y})")
    pyautogui.moveTo(pwd_x, pwd_y, duration=0.7)
    pyautogui.click()
    time.sleep(0.3)

    # 기존 내용 지우기
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.05)
    pyautogui.press('delete')
    time.sleep(0.1)

    # 비밀번호 입력 (interval=0.05 → 매크로 탐지 방지)
    # typewrite는 ASCII만 지원 → 클립보드 폴백 사용
    _pyautogui_type_password(password)
    logger.info("비밀번호 입력 완료 (이미지 매칭 방식)")
    time.sleep(0.3)

    # 확인 버튼 클릭
    confirm_x = left + int(width * _CONFIRM_BTN_REL[0])
    confirm_y = top  + int(height * _CONFIRM_BTN_REL[1])
    logger.info(f"확인 버튼 클릭: ({confirm_x}, {confirm_y})")
    pyautogui.moveTo(confirm_x, confirm_y, duration=0.8)
    time.sleep(0.2)
    pyautogui.click()
    logger.info("확인 버튼 클릭 완료 (이미지 매칭 방식)")
    return True


def _try_keyboard_tab_input(password):
    """
    KSign 팝업이 포커스를 가진 상태에서 Tab → 암호 입력 → Enter.
    이미지 매칭 없이 순수 키보드 이벤트만 사용.
    """
    import pyautogui
    try:
        pyautogui.press('tab')
        time.sleep(0.3)
        _pyautogui_type_password(password)
        time.sleep(0.3)
        pyautogui.press('enter')
        logger.info("키보드 방식 완료: Tab + 암호 + Enter")
        time.sleep(2.0)  # 인증 처리 대기
    except Exception as e:
        logger.warning(f"키보드 방식 오류: {e}")


def _focus_cert_window_if_visible():
    """인증서 창이 있으면 포커스 이동. 없으면 무시."""
    CONFIRM_LABELS = ('확인', 'OK', '로그인', '인증')
    SKIP_CLASSES = ('Shell_TrayWnd', 'Progman', 'WorkerW', 'Chrome_WidgetWin_1',
                    'IME', 'MSCTFIME UI', 'Default IME', 'tooltips_class32', 'SysShadow')
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="win32").windows():
            try:
                cn = w.class_name()
                if cn in SKIP_CLASSES:
                    continue
                rect = w.rectangle()
                w_px = rect.right - rect.left
                h_px = rect.bottom - rect.top
                if w_px < 100 or h_px < 80:
                    continue
                edits = w.descendants(control_type="Edit")
                btns = [b for b in w.descendants(control_type="Button")
                        if b.window_text().strip() in CONFIRM_LABELS]
                if edits and btns:
                    title = w.window_text().strip()
                    logger.info(f"[포커스] 인증서 창 포커스 설정: {title!r} ({cn})")
                    try:
                        w.set_focus()
                    except Exception:
                        pass
                    return
            except Exception:
                pass
    except Exception:
        pass


def _pyautogui_type_password(password):
    """
    비밀번호를 pyautogui로 입력한다.
    ASCII 문자 → typewrite (interval 적용)
    비ASCII 포함 → 클립보드 붙여넣기
    """
    import pyautogui

    if all(ord(c) < 128 for c in password):
        pyautogui.typewrite(password, interval=0.05)
    else:
        # 클립보드 경유 입력
        _set_clipboard(password)
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
