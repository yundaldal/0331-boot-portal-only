# 빌드 및 배포 가이드

## 개발 환경 셋업

```bash
# 1. 가상 환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate

# 2. 의존성 설치
pip install -r requirements.txt
```

## 개발 중 실행 (콘솔 표시)

```bash
python main.py
```

## .exe 빌드

```bash
# 단일 .exe 파일 생성 (콘솔 창 숨김)
pyinstaller --onefile --noconsole --name AutoLogin main.py

# 결과물: dist\AutoLogin.exe
```

### 빌드 옵션 설명

| 옵션 | 설명 |
|------|------|
| `--onefile` | 단일 .exe로 패키징 |
| `--noconsole` | 콘솔 창 숨김 (배포용) |
| `--name AutoLogin` | 출력 파일명 |
| `--icon=app.ico` | (선택) 아이콘 지정 |

### 디버깅 빌드 (콘솔 표시)

```bash
pyinstaller --onefile --name AutoLogin_debug main.py
```

## 배포

- `dist\AutoLogin.exe` 파일만 배포
- 최초 실행 시 `config.ini`가 자동 생성됨
- 실행 결과는 `autologin.log`에 기록됨

## 주의사항

1. **백신 차단**: PyInstaller 빌드 파일은 백신에 의해 오탐될 수 있음
   → 배포 전 주요 백신 예외 등록 안내 동봉 권장

2. **Chrome 필수**: 대상 PC에 Chrome 브라우저가 설치되어 있어야 함
   → ChromeDriver는 `webdriver-manager`가 자동 다운로드

3. **인터넷 연결**: 첫 실행 시 ChromeDriver 다운로드를 위해 인터넷 필요

4. **KSign 창 제목 확인**: 실제 환경에서 인증서 창 제목이 다를 경우
   → `cert_window_handler.py`의 `CERT_WINDOW_TITLES` 리스트에 추가

5. **pywin32 포함**: `pywin32`는 pywinauto 의존성으로 함께 설치됨
   → PyInstaller 빌드 시 자동 포함되나, 오류 시 `--collect-all pywin32` 추가
