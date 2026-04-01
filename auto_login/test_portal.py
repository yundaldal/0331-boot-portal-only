"""업무포털 로그인만 단독 테스트 (브라우저 선택 가능)"""
import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

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
logger.info(f"결과: {'성공' if result else '실패'}")
