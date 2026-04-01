# REQUIREMENTS.md — 업무포털 자동 로그인 프로그램

## 목표

1. **부팅 시 자동 실행**: Windows 부팅 후 자동로그인.exe가 Run 레지스트리(또는 Task Scheduler 폴백)를 통해 자동 시작된다.
2. **업무포털 자동 로그인**: Chrome subprocess 실행 → 교육청 업무포털 인증서 버튼 클릭 → KSign 암호 입력 → 로그인 완료.
3. **다중 사용자 배포**: 다른 Windows 환경 사용자에게 onedir 폴더로 배포 가능.

## 비목표

- Selenium/ChromeDriver 단독 사용 (nProtect 감지 우회 불가, subprocess 방식 우선).
- GEN 메신저 로그인 (v2에서 분리 완료).
- Linux/macOS 지원.
- 인증서 암호 암호화 저장 (부팅 자동화 특성상 평문 필수).
- 관리자 권한 강제 요구 (HighestAvailable로 가능한 범위 내 동작).

## 성공 기준

| # | 기준 | 검증 방법 |
|---|------|----------|
| 1 | 부팅 후 자동로그인.exe 자동 시작 | Run 레지스트리 또는 Task Scheduler에 AutoLogin 등록 확인 |
| 2 | 업무포털 로그인 성공 | autologin.log에서 "업무포털 로그인 성공" 확인 |
| 3 | autologin.log가 exe 옆에 생성 | dist/자동로그인/autologin.log 존재 확인 |
| 4 | exe 재실행 시 시작프로그램 자가 복구 | Run 키 삭제 후 exe 수동 실행 → 재등록 확인 |
