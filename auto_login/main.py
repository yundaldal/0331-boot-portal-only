"""
교육청 업무포털 자동 로그인 프로그램
Entry point — 전체 실행 흐름 오케스트레이션
"""

import sys
import os

# ── PyInstaller .exe 빌드 호환 경로 설정 ─────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# config.ini / autologin.log 를 실행 파일과 같은 폴더에 생성
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)
# ─────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import messagebox

import logger_setup
import config_manager
import setup_gui
import portal_login


def _ask_popup(title, message):
    """Yes/No 팝업. True=Yes, False=No"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    result = messagebox.askyesno(title, message, parent=root)
    root.destroy()
    return result


def _info_popup(title, message):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def _error_popup(title, message):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showerror(title, message, parent=root)
    root.destroy()


def _set_high_priority():
    """현재 프로세스 우선순위를 HIGH_PRIORITY_CLASS로 설정."""
    try:
        import win32api
        import win32process
        import win32con
        handle = win32api.GetCurrentProcess()
        win32process.SetPriorityClass(handle, win32con.HIGH_PRIORITY_CLASS)
    except Exception:
        pass  # 권한 부족 등 실패해도 계속 진행


def main():
    _set_high_priority()
    logger = logger_setup.setup_logger()
    logger.info("=" * 50)
    logger.info("프로그램 시작")

    # ── Step 1: 설정 파일 확인 ────────────────────────────────────
    if not config_manager.config_exists():
        logger.info("config.ini 없음 또는 불완전 → 설정 GUI 표시")
        saved = setup_gui.run_setup_gui()
        if not saved:
            logger.info("설정 저장 취소 → 프로그램 종료")
            return
        logger.info("설정 저장 완료 → 로그인 단계 진행")

    # ── Step 2: 설정 로드 ─────────────────────────────────────────
    try:
        settings, advanced = config_manager.load_config()
    except Exception as e:
        logger.error(f"config.ini 로드 실패: {e}")
        _error_popup(
            '설정 오류',
            f'설정 파일을 읽을 수 없습니다.\n({e})\n\n설정을 다시 입력합니다.'
        )
        config_manager.delete_config()
        saved = setup_gui.run_setup_gui()
        if not saved:
            return
        settings, advanced = config_manager.load_config()

    boot_option = settings.get('boot_option', 'auto')
    logger.info(f"config.ini 로드 완료 (boot_option={boot_option})")

    # ── Step 2.5: Task Scheduler 자가 복구 ──────────────────────
    if getattr(sys, 'frozen', False) and boot_option in ('auto', 'ask'):
        try:
            if not config_manager.startup_task_exists():
                logger.info("AutoLogin 태스크 미등록 → 자동 등록 시도")
                config_manager.register_startup()
        except Exception as e:
            logger.warning(f"Task Scheduler 등록 확인 실패 (무시): {e}")

    # ── Step 3: 부팅 옵션 처리 ───────────────────────────────────
    if boot_option == 'ask':
        logger.info("boot_option=ask → 실행 여부 팝업 표시")
        proceed = _ask_popup('자동 로그인', '자동 로그인을 시작하시겠습니까?')
        if not proceed:
            logger.info("사용자 No 선택 → 프로그램 종료")
            return
        logger.info("사용자 Yes 선택 → 로그인 진행")
    else:
        logger.info("boot_option=auto → 팝업 없이 로그인 진행")

    # ── Step 4: 업무포털 로그인 ───────────────────────────────────
    portal_url = settings.get('portal_url', 'https://gen.eduptl.kr/bpm_lgn_lg00_001.do')

    browser_ready = False
    try:
        browser_ready = portal_login.prepare_browser(portal_url, settings)
    except Exception as e:
        logger.error(f"브라우저 사전 준비 실패: {e}")

    try:
        portal_ok = portal_login.login(settings, advanced, chrome_ready=browser_ready)
    except Exception as e:
        logger.error(f"포털 로그인 예외: {e}")
        portal_ok = False

    logger.info(f"로그인 결과 — 포털: {'성공' if portal_ok else '실패'}")

    if portal_ok:
        # ── Step 5: 로그인 후 추가 서비스 열기 (나이스 / K-에듀파인) ──
        after_login = settings.get('after_login', 'none')
        if after_login != 'none':
            logger.info(f"추가 서비스 열기: {after_login}")
            try:
                portal_login.open_additional_services(settings)
            except Exception as e:
                logger.error(f"추가 서비스 열기 중 예외: {e}")

        _info_popup('로그인 완료', '업무포털 로그인이 완료되었습니다.')
    else:
        _error_popup('로그인 실패', '업무포털 자동 로그인에 실패했습니다.\n\nautologin.log를 확인해 주세요.')


if __name__ == '__main__':
    main()
