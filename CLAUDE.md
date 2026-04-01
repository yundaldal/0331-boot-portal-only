# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Windows 부팅 시 교육청 업무포털(eduptl.kr)에 자동 로그인하는 프로그램. 전국 17개 시도교육청 지원, Chrome/Edge 브라우저 선택 가능. onedir 폴더 형태로 배포. 모든 소스 코드는 `auto_login/` 디렉토리에 있다.

## 개발 명령

```bash
# 가상환경 활성화 (auto_login/ 디렉토리 안에서)
venv\Scripts\activate

# 전체 실행 (개발 중 테스트)
venv\Scripts\python.exe main.py

# 업무포털 로그인만 단독 테스트
venv\Scripts\python.exe test_portal.py

# 창 제목 진단 (KSign 실제 창 제목 파악용)
venv\Scripts\python.exe check_windows.py

# PyInstaller 빌드 (spec 파일 사용 권장, onedir 방식)
venv\Scripts\python.exe -m PyInstaller autologin.spec --distpath dist --workpath build --noconfirm
# 결과물: dist/자동로그인/자동로그인.exe (폴더 배포)

# OneDrive 폴더에서 빌드 시 PermissionError가 반복되면 외부 경로로 빌드 후 복사 (권장)
venv\Scripts\python.exe -m PyInstaller autologin.spec --distpath C:\Temp\autologin_dist --workpath build --noconfirm
rm -rf dist/자동로그인 && cp -r C:/Temp/autologin_dist/자동로그인 dist/자동로그인
```

## 아키텍처

```
main.py                 ← 진입점, 순차 실행 흐름
├── setup_gui.py        ← Tkinter 초기 설정 GUI (교육청 드롭다운 + 브라우저 선택)
├── config_manager.py   ← config.ini 읽기/쓰기 + Windows 시작프로그램 등록(winreg)
├── logger_setup.py     ← RotatingFileHandler (autologin.log, 5MB×3)
└── portal_login.py     ← 업무포털 로그인 (Chrome/Edge subprocess + pyautogui/UIA)
    └── cert_window_handler.py  ← KSign 인증서 창 처리 + 팝업 제거
```

**실행 흐름**: config.ini 확인 → (없으면 설정 GUI) → Task Scheduler 자가 복구 → 부팅 옵션 처리 → `prepare_browser()` → `login()` → `_verify_login_success()` → `open_additional_services()` → 결과 팝업

## 업무포털 로그인 방식

### 1순위: subprocess + UIA (`_login_via_existing_browser`)
1. `prepare_browser()`: 브라우저 종료 → 잠금 파일/복원 다이얼로그 정리 → 플래그 없이 `subprocess.Popen` 실행 → 창 대기
2. `_bring_browser_to_front()`: 다른 프로그램이 가릴 때 `SetForegroundWindow`로 복원
3. 인증서 버튼 탐색 (UIA ID 기반, 40회×0.5초):
   - **1순위**: `auto_id='btnLgn'` (전 지역 공통 HTML element ID)
   - **2순위**: 텍스트 매칭 (`교육행정 전자서명 인증서 로그인` 등)
   - **3순위**: 부분 텍스트 (`'인증서' in text and '로그인' in text`)
4. `_portal_keyboard_cert_flow()`: Tab → 클립보드 암호 → Enter (2.5초마다 재시도, timeout=90초)
5. `_verify_login_success()`: `btnLgn` 소멸을 최대 20초 폴링 → 실패 시 Selenium fallback 진행

### 2순위: Selenium WebDriver 폴백 (`_login_via_selenium`)
UIA 방식 실패 시 Selenium으로 재시도. Chrome/Edge 모두 지원 (`webdriver_manager` 자동 드라이버 관리).
`CERT_BTN_SELECTORS` 리스트로 `#btnLgn` ID → 텍스트 → 클래스 순 셀렉터 시도.

## 브라우저 지원 (Chrome/Edge)

`BROWSER_PROFILES` dict로 브라우저별 설정을 추상화:
- `exe_paths`: 실행 파일 경로 후보 리스트
- `process_name`: `chrome.exe` / `msedge.exe` (taskkill 대상)
- `user_data_dir`: 사용자 프로파일 경로 (NPKI/CrossEx 확장 유지)
- `display_name`: 로그 표시용

`_get_profile(settings)` → 모든 함수가 profile dict 기반으로 동작.
Chrome과 Edge 모두 `Chrome_WidgetWin_1` 윈도우 클래스를 사용하므로 UIA 탐색 코드는 공통.

## 17개 시도교육청 지원

`setup_gui.py`의 `REGIONS` 리스트에 영문코드+표시명 매핑. 포털 URL은 `https://{code}.eduptl.kr/bpm_lgn_lg00_001.do` 패턴으로 생성. 로그인 버튼 ID(`btnLgn`)는 전 지역 공통.

## 핵심 설계 결정

### nProtect 우회
업무포털은 `--remote-debugging-port` 등 자동화 플래그를 감지하여 브라우저를 강제 종료함.
- 1순위에서 Selenium/ChromeDriver 미사용 — `subprocess.Popen`으로 플래그 없이 직접 실행
- KSign 팝업은 브라우저 내부 오버레이 → pywinauto `descendants()` 접근 불가 → 키보드(Tab+Enter) 방식

### pyautogui.FAILSAFE = False
`cert_window_handler.py`와 `portal_login.py` 모듈 상단에 설정 필수.
마우스가 화면 모서리로 이동할 때 `FailSafeException` 발생하여 자동화 중단됨.

### 비ASCII 암호 입력
`type_keys()`는 `()` 등 특수문자를 pywinauto 그룹 연산자로 해석해 오동작.
암호는 항상 클립보드 경유 → `Ctrl+V` 붙여넣기 방식 사용.

### subprocess 콘솔 창 억제
모든 `subprocess.run()` / `Popen()` 호출에 `creationflags=subprocess.CREATE_NO_WINDOW` 필수.
누락 시 `tasklist`, `taskkill`, `schtasks` 등 실행마다 콘솔 창이 순간 깜빡임.

### 브라우저 창 감지 (Electron 앱 오인 방지)
`_wait_for_browser_window(existing_hwnds=...)`: 브라우저 실행 전 기존 `Chrome_WidgetWin_1` 핸들을 저장 후, 신규 핸들만 브라우저로 인식. Cursor, VS Code 등 Electron 앱도 동일 클래스를 사용하므로 이 필터 필수.

### 이미지 파일 로드 (한글 경로 대응)
`cert_window_handler.load_image()` 헬퍼로 PIL Image 객체 로드 후 `pyautogui.locateOnScreen(PIL_Image, ...)` 전달. OpenCV `imread()`는 Windows에서 비ASCII(한글) 경로를 읽지 못함.

### Windows 시작프로그램 등록
`save_config()` 호출 시 `register_startup()` 실행. `boot_option=auto/ask`이면 등록, 그 외 삭제. 비 frozen 환경에서는 등록 안 함.

등록 우선순위 (교육청 GPO가 작업 스케줄러를 차단하는 환경 대응):
1. **1순위: `HKCU\...\Run` 레지스트리** — GPO 영향 없음, 로그온 즉시 실행
2. **2순위: 작업 스케줄러 XML** — HighestAvailable → LeastPrivilege 순 폴백

- `_cleanup_old_startup()`: 구버전 Run 항목 + 시작 폴더 바로가기(`자동로그인.lnk`) 정리
- **자가 복구**: `main.py`에서 매 실행 시 `startup_task_exists()` 확인 → 미등록이면 자동 재등록

### PyInstaller 경로 처리 (onedir 방식)
- `config_manager.py`, `main.py`: `sys.executable` 기준으로 config.ini, log 생성
- `logger_setup.py`: frozen 환경에서 `os.path.dirname(sys.executable)` 사용 (PyInstaller 6.x에서 `__file__`이 `_internal/` 반환하는 문제 방지)
- `autologin.spec`은 `console=False` — 콘솔 창 없이 실행되어야 부팅 시 포커스 충돌 방지

### 다중 모니터 / 해상도 대응
- `cert_window_handler.locate_on_all_screens()`: `ImageGrab.grab(all_screens=True)` + 가상 데스크톱 좌표 변환
- `_find_cert_btn_via_uia()`: UIA `rectangle()` 반환 좌표가 가상 데스크톱 절대 좌표이므로 해상도 무관
- DPI 보정: `ctypes.windll.shcore.SetProcessDpiAwareness(2)` 호출

### 브라우저 종료 대기 (동적 폴링)
`_wait_browser_exit(timeout=5)`: taskkill 후 0.1초 단위로 프로세스 종료 확인. 즉시 종료되면 즉시 다음 단계. 고정 sleep 미사용.

## 로그인 후 추가 서비스 열기 (`open_additional_services`)

`after_login` 설정에 따라 포털 로그인 성공 후 나이스/K-에듀파인을 새 탭으로 열기.

**버튼 탐색 우선순위**:
1. 이미지 매칭 (`neis_ref.png` / `edufine_ref.png`, confidence 0.85→0.75→0.65 단계 시도)
2. UIA Hyperlink AutomationId — 지역 코드 포함 URL 패턴 (`{region}.neis.go.kr`, `klef.{region}.go.kr`)
3. UIA 텍스트 매칭 (`나이스` / `에듀파인`)

**Chrome/Edge 역전 현상**: Chrome에서 나이스 버튼 `@id`는 `klef.{region}.go.kr`, Edge는 `{region}.neis.go.kr`로 브라우저마다 URL이 역전됨. 이미지 매칭이 1순위인 이유.

**Ctrl+클릭**: 모든 서비스 버튼 클릭 시 Ctrl+클릭으로 새 탭 강제 → 포털 탭 유지 (`both` 모드에서 첫 클릭이 페이지 이탈하지 않음).

**배너 처리**: 버튼 클릭 전 `_dismiss_portal_banners()`로 닫기/확인 버튼 자동 클릭. 지역코드 추출: `_extract_region(portal_url)` → `https://gen.eduptl.kr/...` → `gen`.

## 데이터 파일

| 파일 | 용도 | spec 포함 |
|------|------|-----------|
| `ksign_ref.png` | KSign 창 이미지 매칭 (cert_window_handler) | O |
| `neis_ref.png` | 나이스 버튼 이미지 매칭 (portal_login) | O |
| `edufine_ref.png` | K-에듀파인 버튼 이미지 매칭 (portal_login) | O |

참조 이미지 로드: `portal_login._get_ref_image(filename)` — frozen/dev 환경 모두 대응.
인증서 로그인 버튼은 이미지 매칭 없이 UIA `auto_id='btnLgn'` 기반으로 탐색.

## 설정 파일 (`config.ini`)

exe 옆에 자동 생성. 초기화 시 파일 삭제 후 exe 재실행.

```ini
[Settings]
cert_password = ****               # 평문 저장 (부팅 자동화 필수)
boot_option   = auto               # auto | ask
portal_url    = https://gen.eduptl.kr/bpm_lgn_lg00_001.do
browser       = chrome             # chrome | edge
after_login   = none               # none | neis | edufine | both

[Advanced]
cert_window_timeout = 120
poll_interval = 2
```

`after_login`은 선택 항목이므로 기존 config.ini에 없어도 `none`으로 기본 동작 (`setdefault` 처리).

## 참조 문서

- `auto_login/REQUIREMENTS.md` — 목표, 비목표, 성공 기준 정의
- `auto_login/DECISIONS.md` — 주요 설계 변경 기록과 근거

## 주의사항

- `venv/`, `dist/`, `build/` 폴더는 읽지 말 것
- PyInstaller 빌드 시 `pywin32` 오류 발생하면 `--collect-all pywin32` 추가
- `autologin.spec` hiddenimports에 `win32com`, `win32com.client`, `win32com.shell` 포함 필수
- 빌드 전 `dist\자동로그인\자동로그인.exe`가 실행 중이거나 OneDrive 동기화 중이면 PermissionError 발생

## 소통 규칙

- 코드 수정 후 변경 핵심만 3줄 이내로 요약
- 파급 범위 큰 변경은 계획서 먼저 제시 후 승인받고 진행
- 작고 안전한 단위로 수정하여 1차 확인 후 다음 단계 진행
