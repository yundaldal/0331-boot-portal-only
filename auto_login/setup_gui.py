import tkinter as tk
from tkinter import messagebox, ttk
import config_manager


# 시도교육청 목록 (영문약자, 표시명)
REGIONS = [
    ('sen', '서울특별시'),
    ('pen', '부산광역시'),
    ('dge', '대구광역시'),
    ('ice', '인천광역시'),
    ('gen', '광주광역시'),
    ('dje', '대전광역시'),
    ('use', '울산광역시'),
    ('sje', '세종특별자치시'),
    ('goe', '경기도'),
    ('kwe', '강원특별자치도'),
    ('cbe', '충청북도'),
    ('cne', '충청남도'),
    ('jbe', '전북특별자치도'),
    ('jne', '전라남도'),
    ('gbe', '경상북도'),
    ('gne', '경상남도'),
    ('jje', '제주특별자치도'),
]

REGION_DISPLAY = [f'{name} ({code})' for code, name in REGIONS]
REGION_CODES = [code for code, _ in REGIONS]

BROWSERS = [
    ('chrome', 'Chrome'),
    ('edge', 'Edge'),
]
BROWSER_DISPLAY = [name for _, name in BROWSERS]
BROWSER_KEYS = [key for key, _ in BROWSERS]


def _code_to_url(code):
    return f'https://{code}.eduptl.kr/bpm_lgn_lg00_001.do'


def _url_to_index(url):
    """기존 config의 portal_url에서 지역 인덱스를 찾는다."""
    for i, code in enumerate(REGION_CODES):
        if f'{code}.eduptl.kr' in url:
            return i
    return None  # 매칭 안 되면 None


def run_setup_gui():
    """
    초기 설정 GUI를 표시하고 저장 성공 여부(bool)를 반환.
    '저장' 클릭 후 창이 닫히면 True, 창을 그냥 닫으면 False.
    """
    saved = [False]

    root = tk.Tk()
    root.title('자동 로그인 초기 설정')
    root.resizable(False, False)
    root.attributes('-topmost', True)

    # ── 레이아웃 ──────────────────────────────────────
    pad = {'padx': 10, 'pady': 8}

    # 소속 교육청
    tk.Label(root, text='소속 교육청 *', anchor='w').grid(
        row=0, column=0, sticky='w', **pad)

    region_var = tk.StringVar()
    region_combo = ttk.Combobox(
        root, textvariable=region_var, values=REGION_DISPLAY,
        state='readonly', width=39,
    )
    region_combo.grid(row=0, column=1, columnspan=2, padx=(0, 10), pady=8)

    # 브라우저 선택
    tk.Label(root, text='브라우저 *', anchor='w').grid(
        row=1, column=0, sticky='w', **pad)

    browser_var = tk.StringVar()
    browser_combo = ttk.Combobox(
        root, textvariable=browser_var, values=BROWSER_DISPLAY,
        state='readonly', width=39,
    )
    browser_combo.grid(row=1, column=1, columnspan=2, padx=(0, 10), pady=8)
    browser_combo.current(0)  # 기본값: Chrome

    # 기존 config가 있으면 해당 지역/브라우저 선택
    try:
        settings, _ = config_manager.load_config()
        idx = _url_to_index(settings.get('portal_url', ''))
        if idx is not None:
            region_combo.current(idx)
        browser_key = settings.get('browser', 'chrome')
        if browser_key in BROWSER_KEYS:
            browser_combo.current(BROWSER_KEYS.index(browser_key))
    except Exception:
        pass

    # 인증서 비밀번호 (평문 표시 — 오타 방지)
    tk.Label(root, text='인증서 비밀번호 *', anchor='w').grid(
        row=2, column=0, sticky='w', **pad)

    password_var = tk.StringVar()
    tk.Entry(root, textvariable=password_var, width=42).grid(
        row=2, column=1, columnspan=2, padx=(0, 10), pady=8)

    # 부팅 옵션
    tk.Label(root, text='부팅 시 실행 옵션 *', anchor='w').grid(
        row=3, column=0, sticky='w', **pad)

    boot_var = tk.StringVar(value='auto')
    opt_frame = tk.Frame(root)
    opt_frame.grid(row=3, column=1, columnspan=2, sticky='w', padx=(0, 10), pady=4)

    tk.Radiobutton(
        opt_frame, text='윈도우 시작 시 자동 실행 (팝업 없음)',
        variable=boot_var, value='auto'
    ).pack(anchor='w')
    tk.Radiobutton(
        opt_frame, text='실행 여부 묻기 팝업 띄우기',
        variable=boot_var, value='ask'
    ).pack(anchor='w')

    # 로그인 후 열기 (업무포털은 항상 열림)
    tk.Label(root, text='로그인 후 열기', anchor='w').grid(
        row=4, column=0, sticky='nw', **pad)

    after_var = tk.StringVar(value='none')
    after_frame = tk.Frame(root)
    after_frame.grid(row=4, column=1, columnspan=2, sticky='w', padx=(0, 10), pady=4)

    tk.Radiobutton(after_frame,
                   text='업무포털만',
                   variable=after_var, value='none').pack(anchor='w')
    tk.Radiobutton(after_frame,
                   text='업무포털  +  나이스',
                   variable=after_var, value='neis').pack(anchor='w')
    tk.Radiobutton(after_frame,
                   text='업무포털  +  K-에듀파인',
                   variable=after_var, value='edufine').pack(anchor='w')
    tk.Radiobutton(after_frame,
                   text='업무포털  +  나이스  +  K-에듀파인',
                   variable=after_var, value='both').pack(anchor='w')

    # 기존 config 있으면 after_login 값 복원
    try:
        settings, _ = config_manager.load_config()
        al = settings.get('after_login', 'none')
        if al in ('none', 'neis', 'edufine', 'both'):
            after_var.set(al)
    except Exception:
        pass

    # 구분선
    tk.Frame(root, height=1, bg='#cccccc').grid(
        row=5, column=0, columnspan=3, sticky='ew', padx=10, pady=4)

    # 저장 버튼
    def save():
        pwd = password_var.get().strip()
        boot = boot_var.get()
        region_idx = region_combo.current()
        browser_idx = browser_combo.current()
        after = after_var.get()

        if region_idx < 0:
            messagebox.showwarning('입력 오류', '소속 교육청을 선택해 주세요.', parent=root)
            return
        if not pwd:
            messagebox.showwarning('입력 오류', '인증서 비밀번호를 입력해 주세요.', parent=root)
            return

        portal_url = _code_to_url(REGION_CODES[region_idx])
        browser = BROWSER_KEYS[browser_idx]
        config_manager.save_config(pwd, boot, portal_url, browser, after_login=after)
        saved[0] = True
        messagebox.showinfo(
            '저장 완료',
            '설정이 저장되었습니다.\n프로그램을 다시 실행하면 자동 로그인이 시작됩니다.',
            parent=root,
        )
        root.destroy()

    tk.Button(
        root, text='저장', command=save,
        width=16, bg='#4CAF50', fg='white', font=('', 10, 'bold')
    ).grid(row=6, column=0, columnspan=3, pady=12)

    # 창 중앙 정렬
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f'+{(sw - w) // 2}+{(sh - h) // 2}')

    root.protocol('WM_DELETE_WINDOW', root.destroy)
    root.mainloop()

    return saved[0]
