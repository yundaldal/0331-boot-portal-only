# DECISIONS.md — 중요 결정 기록

## 2026-03-31: 메신저 기능 분리 → 업무포털 전용 프로그램으로 전환

**무엇**: messenger_login.py 삭제, main.py에서 메신저 스레드/import 제거, setup_gui에서 메신저 경로 필드 제거, config_manager에서 find_messenger_path() 삭제, portal_login에서 ucware 관련 함수 3개 삭제, autologin.spec에서 메신저 전용 이미지 3개 제거.

**왜**:
- 메신저와 포털 기능이 코드상 엉켜 있어 유지보수/디버깅이 어려움.
- 업무포털만 단독으로 가볍게 실행하려는 요구.
- 두 기능은 실행 흐름이 완전 독립(별도 스레드)이어서 분리 시 포털 로직에 영향 없음.

**삭제 범위**:
- 파일: messenger_login.py, test_messenger.py
- 함수: find_messenger_path(), _get_ucware_pid(), _minimize_ucware_windows(), _is_ucware_covering()
- GUI: 메신저 경로 입력/자동탐색/찾아보기
- 이미지: messenger_logged_in_ref.png, tray_btn.png, minimize_btn.png (spec에서 제거)

**보존**: cert_window_handler.py(포털 인증서 처리에 사용), logger_setup.py, config_manager.py(시작프로그램 등록)

## 2026-03-23: Task Scheduler 자가 복구 메커니즘 추가

**무엇**: `main.py`에서 매 실행 시 `startup_task_exists()` 확인 → 미등록 시 `register_startup()` 호출.

**왜**:
- 3/20 이후 AutoLogin 태스크가 소실되어 3/21~3/23 부팅 시 프로그램이 실행되지 않음.
- `register_startup()`이 `save_config()`에서만 호출되어, 리빌드/재설치/태스크 수동 삭제 시 복구 불가.
- `schtasks /Create /F`는 멱등(idempotent)이므로 매 실행 시 호출해도 부작용 없음.

## 2026-03-23: logger_setup.py 로그 경로 수정

**무엇**: frozen 환경에서 `os.path.abspath(__file__)` → `os.path.dirname(sys.executable)` 변경.

**왜**:
- PyInstaller 6.x에서 `__file__`이 `_internal/` 경로를 반환하여 로그가 `_internal/autologin.log`에 생성됨.
- 사용자와 배포 대상이 로그 파일을 exe 옆에서 찾을 수 있어야 함.
