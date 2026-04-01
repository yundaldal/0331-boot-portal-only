"""업무포털 로그인만 단독 테스트 (브라우저 선택 가능)"""
import sys, os, tkinter as tk
from tkinter import messagebox
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


def _notify(title, message, error=False):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    if error:
        messagebox.showerror(title, message, parent=root)
    else:
        messagebox.showinfo(title, message, parent=root)
    root.destroy()

import logger_setup, config_manager, portal_login

logger = logger_setup.setup_logger()
settings, advanced = config_manager.load_config()

# 커맨드라인 인자로 브라우저 선택: python test_portal.py edge
if len(sys.argv) > 1 and sys.argv[1] in ('chrome', 'edge'):
    settings['browser'] = sys.argv[1]

browser = settings.get('browser', 'chrome')
portal_url = settings.get('portal_url', 'https://gen.eduptl.kr/bpm_lgn_lg00_001.do')
logger.info(f"업무포털 단독 테스트 시작 (browser={browser})")

browser_ready = False
try:
    browser_ready = portal_login.prepare_browser(portal_url, settings)
except Exception as e:
    logger.error(f"브라우저 사전 준비 실패: {e}")

result = portal_login.login(settings, advanced, chrome_ready=browser_ready)
logger.info(f"로그인 결과: {'성공' if result else '실패'}")

if result:
    after_login = settings.get('after_login', 'none')
    if after_login != 'none':
        logger.info(f"추가 서비스 열기 시작: {after_login}")
        portal_login.open_additional_services(settings)
    else:
        logger.info("after_login=none → 추가 서비스 없음")
    _notify('로그인 완료', '업무포털 로그인이 완료되었습니다.')
else:
    _notify('로그인 실패', '업무포털 자동 로그인에 실패했습니다.\nautologin.log를 확인해 주세요.', error=True)
