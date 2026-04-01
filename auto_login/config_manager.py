import configparser
import logging
import os
import subprocess
import sys
import tempfile
import winreg

logger = logging.getLogger('AutoLogin')

STARTUP_REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
STARTUP_APP_NAME = 'AutoLogin'
TASK_NAME = 'AutoLogin'

# PyInstaller 빌드 시 exe 위치 기준, 개발 시 소스 폴더 기준
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, 'config.ini')

REQUIRED_KEYS = ['cert_password', 'boot_option', 'portal_url', 'browser']
# after_login은 선택 항목 (기존 config.ini 하위 호환)
AFTER_LOGIN_DEFAULT = 'none'

ADVANCED_DEFAULTS = {
    'cert_window_timeout': '120',
    'poll_interval': '2',
}


def config_exists():
    """config.ini가 존재하고 필수 키가 모두 채워져 있는지 확인"""
    if not os.path.exists(CONFIG_FILE):
        return False
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding='utf-8')
        if 'Settings' not in config:
            return False
        for key in REQUIRED_KEYS:
            if key not in config['Settings'] or not config['Settings'][key].strip():
                return False
        return True
    except Exception:
        return False


def load_config():
    """
    config.ini를 읽어 (settings_dict, advanced_dict) 반환.
    settings_dict : cert_password, boot_option, portal_url, browser
    advanced_dict : cert_window_timeout, poll_interval
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8')

    settings = dict(config['Settings'])
    settings.setdefault('after_login', AFTER_LOGIN_DEFAULT)  # 기존 config 하위 호환

    advanced = dict(config['Advanced']) if 'Advanced' in config else {}
    for key, default in ADVANCED_DEFAULTS.items():
        advanced.setdefault(key, default)

    return settings, advanced


def save_config(cert_password, boot_option, portal_url, browser='chrome', after_login='none'):
    """설정을 config.ini에 저장. 기존 Advanced 섹션은 보존."""
    config = configparser.ConfigParser()

    # 기존 파일 있으면 읽어와서 Advanced 섹션 보존
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')

    settings = {
        'cert_password': cert_password,
        'boot_option': boot_option,
        'portal_url': portal_url,
        'browser': browser,
        'after_login': after_login,
    }
    config['Settings'] = settings

    if 'Advanced' not in config:
        config['Advanced'] = ADVANCED_DEFAULTS

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)

    # 시작 프로그램 등록/해제
    if boot_option in ('auto', 'ask'):
        register_startup()
    else:
        unregister_startup()


def delete_config():
    """config.ini 삭제 (손상 시 재설정 용도)"""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)


def startup_task_exists():
    """AutoLogin이 시작프로그램에 등록되어 있는지 확인 (Run 레지스트리 또는 작업 스케줄러)."""
    # 1순위: HKCU Run 레지스트리 확인
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, STARTUP_APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        pass
    # 2순위: 작업 스케줄러 확인
    try:
        result = subprocess.run(
            ['schtasks', '/Query', '/TN', TASK_NAME],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def register_startup():
    """부팅 시 자동 실행 등록.
    1순위: HKCU Run 레지스트리 (ucware_m.exe와 동일 방식, GPO 영향 없음)
    2순위: 작업 스케줄러 XML (HighestAvailable → LeastPrivilege)
    """
    if not getattr(sys, 'frozen', False):
        return  # 개발 환경에서는 등록하지 않음

    _cleanup_old_startup()

    exe_path = sys.executable
    exe_dir = os.path.dirname(exe_path)

    # ── 1순위: HKCU Run 레지스트리 (ucware_m.exe와 동일 방식) ───────────
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        logger.info(f"레지스트리 Run 등록 성공: {exe_path}")
        return  # 성공 시 즉시 종료
    except Exception as e:
        logger.warning(f"레지스트리 Run 등록 실패: {e} → 작업 스케줄러 시도")

    # ── 2순위: 작업 스케줄러 XML ────────────────────────────────────────
    domain = os.environ.get('USERDOMAIN', '')
    username = os.environ.get('USERNAME', '')
    user_id = f'{domain}\\{username}' if domain and domain != username else username

    for run_level in ('HighestAvailable', 'LeastPrivilege'):
        xml_content = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>업무포털 자동 로그인</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user_id}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>{run_level}</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <Priority>4</Priority>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{exe_path}</Command>
      <WorkingDirectory>{exe_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''

        xml_path = None
        try:
            fd, xml_path = tempfile.mkstemp(suffix='.xml')
            with os.fdopen(fd, 'w', encoding='utf-16') as f:
                f.write(xml_content)

            result = subprocess.run(
                ['schtasks', '/Create', '/TN', TASK_NAME, '/XML', xml_path, '/F'],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                logger.info(f"작업 스케줄러 등록 성공 ({run_level}): {exe_path}")
                return
            else:
                logger.warning(f"작업 스케줄러 등록 실패 ({run_level}, code={result.returncode}): {result.stderr.strip()}")
        except Exception as e:
            logger.error(f"작업 스케줄러 등록 예외 ({run_level}): {e}")
        finally:
            if xml_path and os.path.exists(xml_path):
                os.remove(xml_path)

    logger.error("모든 시작프로그램 등록 방법 실패 (Run 레지스트리 + 작업 스케줄러)")


def unregister_startup():
    """작업 스케줄러에서 태스크 삭제."""
    try:
        subprocess.run(
            ['schtasks', '/Delete', '/TN', TASK_NAME, '/F'],
            capture_output=True, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass
    _cleanup_old_startup()


def _cleanup_old_startup():
    """구버전 레지스트리 Run 항목 + 시작 폴더 바로가기 정리."""
    # 레지스트리 Run 항목 삭제
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, STARTUP_APP_NAME)
        winreg.CloseKey(key)
    except Exception:
        pass

    # 시작 폴더 바로가기 삭제
    lnk_path = os.path.join(
        os.environ.get('APPDATA', ''),
        'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup',
        '자동로그인.lnk',
    )
    try:
        if os.path.exists(lnk_path):
            os.remove(lnk_path)
    except Exception:
        pass
