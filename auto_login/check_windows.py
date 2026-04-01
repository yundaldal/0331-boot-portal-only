"""
버튼 클릭 후 나타나는 창 제목을 실시간으로 출력하는 진단 스크립트.
업무포털 로그인 버튼을 클릭한 뒤 30초간 새로 열리는 모든 창을 캡처합니다.
"""
import time
import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from pywinauto import Desktop

def get_all_windows():
    titles = set()
    try:
        desk = Desktop(backend="uia")
        for w in desk.windows():
            t = w.window_text().strip()
            if t:
                titles.add(t)
    except Exception:
        pass
    return titles

# 버튼 클릭 전 창 목록 기록
print("=== 현재 열린 창 목록 ===")
before = get_all_windows()
for t in sorted(before):
    print(f"  [{t}]")

print("\n업무포털 로그인 버튼을 클릭하세요. 30초간 새 창을 모니터링합니다...\n")

import logger_setup, config_manager, portal_login
logger_setup.setup_logger()
settings, advanced = config_manager.load_config()

# Selenium으로 페이지만 열고 버튼 클릭까지만 수행
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_experimental_option("detach", True)
options.add_experimental_option("excludeSwitches", ["enable-logging"])
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

portal_url = advanced.get('portal_url', 'https://gen.eduptl.kr/bpm_lgn_lg00_001.do')
driver.get(portal_url)
time.sleep(3)

# 권한 팝업 처리
portal_login._handle_chrome_permission_popup(timeout=5)

# 버튼 클릭
btn = portal_login._find_and_click_cert_button(driver)
print(f"버튼 클릭: {'성공' if btn else '실패'}")

# 30초간 새로 열리는 창 모니터링
print("\n=== 새로 나타나는 창 모니터링 (30초) ===")
for i in range(30):
    time.sleep(1)
    after = get_all_windows()
    new_windows = after - before
    if new_windows:
        print(f"[{i+1}초] 새 창 발견!")
        for t in sorted(new_windows):
            print(f"  → 창 제목: [{t}]")
        before = after  # 중복 출력 방지
    else:
        print(f"[{i+1}초] 변화 없음", end="\r")

print("\n\n=== 종료 ===")
