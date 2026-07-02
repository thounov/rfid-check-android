# -*- coding: utf-8 -*-
"""
RFID 팔찌 반납 확인 - Android 독립 앱 (서버 불필요)
Kivy + pyjnius (Android NFC) + SQLite 내장 DB
"""

import os, sys, sqlite3, datetime, json
from functools import partial

# ── Kivy 환경 설정 ────────────────────────────────────────────────
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_ORIENTATION", "PORTRAIT")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.uix.colorpicker import ColorPicker
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.core.window import Window
from kivy.properties import StringProperty

# ── 색상 ─────────────────────────────────────────────────────────
C_BG      = get_color_from_hex("#0f172a")
C_PANEL   = get_color_from_hex("#1e293b")
C_INPUT   = get_color_from_hex("#0b1220")
C_PRIMARY = get_color_from_hex("#3b82f6")
C_TEXT    = get_color_from_hex("#f1f5f9")
C_SUB     = get_color_from_hex("#94a3b8")
C_OK      = get_color_from_hex("#22c55e")
C_WARN    = get_color_from_hex("#ef4444")
C_DUP     = get_color_from_hex("#f59e0b")
C_LOST    = get_color_from_hex("#a855f7")

Window.clearcolor = C_BG

DEFAULT_COLORS = {
    "파랑":  ("#3b82f6", "#ffffff"),
    "노랑":  ("#eab308", "#1a1a1a"),
    "주황":  ("#f97316", "#ffffff"),
    "초록":  ("#22c55e", "#ffffff"),
    "보라":  ("#a855f7", "#ffffff"),
    "빨강":  ("#ef4444", "#ffffff"),
    "회색":  ("#64748b", "#ffffff"),
}

# ── Android NFC ───────────────────────────────────────────────────
ANDROID = False
try:
    from android import activity
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    from jnius import autoclass, cast
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    NfcAdapter     = autoclass("android.nfc.NfcAdapter")
    Intent         = autoclass("android.content.Intent")
    IntentFilter   = autoclass("android.content.IntentFilter")
    PendingIntent  = autoclass("android.app.PendingIntent")
    Tag            = autoclass("android.nfc.Tag")
    ANDROID = True
except Exception:
    pass

# ── 데이터 경로 ───────────────────────────────────────────────────
def get_data_dir():
    try:
        return app_storage_path()
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(get_data_dir(), "rfid_check.db")

def _copy_bundled_db():
    """
    앱 첫 실행 시 번들 DB(소스 폴더의 rfid_check.db)를
    앱 데이터 디렉터리로 복사합니다.
    이미 존재하면 덮어쓰지 않습니다.
    """
    if os.path.exists(DB_PATH):
        return  # 이미 있으면 건드리지 않음

    # 번들 DB 위치 (main.py와 같은 폴더)
    bundle_db = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "rfid_check.db"
    )
    if os.path.exists(bundle_db):
        import shutil
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            shutil.copy2(bundle_db, DB_PATH)
        except Exception as e:
            print(f"번들 DB 복사 실패: {e}")

_copy_bundled_db()

# ════════════════════════════════════════════════════════════════════
# DB 레이어 (PC 앱 main.py Database 클래스와 동일 로직)
# ════════════════════════════════════════════════════════════════════
class Database:
    def __init__(self, path):
        self.path = path
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _init(self):
        conn = self._conn()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bracelets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_code        TEXT UNIQUE NOT NULL,
                display_number  TEXT,
                color_name      TEXT,
                label           TEXT,
                status          TEXT NOT NULL DEFAULT 'unchecked',
                last_checked_at TEXT,
                created_at      TEXT NOT NULL
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS check_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_code   TEXT NOT NULL,
                result     TEXT NOT NULL,
                checked_at TEXT NOT NULL
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS color_palette (
                name       TEXT PRIMARY KEY,
                bg         TEXT NOT NULL,
                fg         TEXT NOT NULL,
                sort_order INTEGER DEFAULT 99
            )""")
        # 마이그레이션
        for col in ("display_number TEXT", "color_name TEXT"):
            try: cur.execute(f"ALTER TABLE bracelets ADD COLUMN {col}")
            except: pass
        # 기본 색상
        for i, (name, (bg, fg)) in enumerate(DEFAULT_COLORS.items()):
            cur.execute("INSERT OR IGNORE INTO color_palette(name,bg,fg,sort_order) VALUES(?,?,?,?)",
                        (name, bg, fg, i))
        conn.commit()
        conn.close()

    # ── 팔찌 ────────────────────────────────────────────────────
    def add_bracelet(self, tag_code, display_number="", color_name="", label=""):
        tag_code = tag_code.strip().upper()
        if not tag_code: return False, "빈 값입니다."
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO bracelets(tag_code,display_number,color_name,label,status,created_at)"
                    " VALUES(?,?,?,?,'unchecked',?)",
                    (tag_code, display_number.strip(), color_name.strip(),
                     label.strip(), datetime.datetime.now().isoformat()))
            return True, "등록되었습니다."
        except sqlite3.IntegrityError:
            return False, "이미 등록된 팔찌 번호입니다."

    def delete_bracelet(self, bid):
        with self._conn() as c:
            c.execute("DELETE FROM bracelets WHERE id=?", (bid,))

    def get_all(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id,tag_code,display_number,color_name,label,status,last_checked_at"
                " FROM bracelets ORDER BY display_number,tag_code"
            ).fetchall()
        return [{"id":r[0],"tag_code":r[1],"display_number":r[2] or "",
                 "color_name":r[3] or "","label":r[4] or "",
                 "status":r[5],"last_checked_at":r[6] or ""} for r in rows]

    def get_counts(self):
        with self._conn() as c:
            rows = c.execute("SELECT status,COUNT(*) FROM bracelets GROUP BY status").fetchall()
        d = dict(rows)
        total = sum(d.values())
        return total, d.get("checked",0), d.get("unchecked",0), d.get("lost",0)

    def reset_all(self):
        with self._conn() as c:
            c.execute("UPDATE bracelets SET status='unchecked',last_checked_at=NULL"
                      " WHERE status != 'lost'")

    def find(self, tag_code):
        with self._conn() as c:
            r = c.execute(
                "SELECT id,tag_code,display_number,color_name,label,status FROM bracelets WHERE tag_code=?",
                (tag_code.strip().upper(),)
            ).fetchone()
        if r is None: return None
        return {"id":r[0],"tag_code":r[1],"display_number":r[2] or "",
                "color_name":r[3] or "","label":r[4] or "","status":r[5]}

    def mark_checked(self, tag_code):
        row = self.find(tag_code)
        now = datetime.datetime.now().isoformat()
        with self._conn() as c:
            if row is None:
                result, dn, cn, lb = "unknown", "", "", ""
            else:
                dn, cn, lb, status = row["display_number"], row["color_name"], row["label"], row["status"]
                if status == "checked":   result = "duplicate"
                elif status == "lost":    result = "lost"
                else:
                    result = "ok"
                    c.execute("UPDATE bracelets SET status='checked',last_checked_at=? WHERE tag_code=?",
                              (now, tag_code.strip().upper()))
            c.execute("INSERT INTO check_log(tag_code,result,checked_at) VALUES(?,?,?)",
                      (tag_code, result, now))
        return result, dn, cn, lb

    def set_status(self, tag_code, status):
        now = datetime.datetime.now().isoformat() if status == "checked" else None
        with self._conn() as c:
            c.execute("UPDATE bracelets SET status=?,last_checked_at=? WHERE tag_code=?",
                      (status, now, tag_code.strip().upper()))

    # ── 색상 ────────────────────────────────────────────────────
    def get_colors(self):
        with self._conn() as c:
            return [{"name":r[0],"bg":r[1],"fg":r[2]}
                    for r in c.execute("SELECT name,bg,fg FROM color_palette ORDER BY sort_order,name").fetchall()]

    def color_map(self):
        return {r["name"]:(r["bg"],r["fg"]) for r in self.get_colors()}

    def add_color(self, name, bg, fg):
        try:
            with self._conn() as c:
                c.execute("INSERT INTO color_palette(name,bg,fg,sort_order) VALUES(?,?,?,99)",
                          (name.strip(), bg, fg))
            return True, "추가되었습니다."
        except sqlite3.IntegrityError:
            return False, "이미 있는 색상 이름입니다."

    def delete_color(self, name):
        with self._conn() as c:
            c.execute("DELETE FROM color_palette WHERE name=?", (name,))


# ════════════════════════════════════════════════════════════════════
# 공통 UI 헬퍼
# ════════════════════════════════════════════════════════════════════
def lbl(text, size=14, color=C_TEXT, bold=False, halign="left",
        h=None, **kw):
    l = Label(text=text, font_size=sp(size), color=color, bold=bold,
              halign=halign, valign="middle",
              size_hint_y=None, height=dp(h or 32), **kw)
    l.bind(size=l.setter("text_size"))
    return l

def btn(text, bg=C_PRIMARY, fg=None, h=44, fs=14, on_press=None, **kw):
    b = Button(text=text, font_size=sp(fs),
               background_normal="", background_color=bg,
               color=fg or [1,1,1,1],
               size_hint_y=None, height=dp(h), **kw)
    if on_press: b.bind(on_press=on_press)
    return b

def inp(hint="", text="", **kw):
    return TextInput(
        hint_text=hint, text=text,
        background_color=C_INPUT, foreground_color=C_TEXT,
        hint_text_color=C_SUB, cursor_color=C_TEXT,
        font_size=sp(14), multiline=False,
        size_hint_y=None, height=dp(44),
        padding=[dp(10), dp(10)], **kw)

def panel_bg(widget, color=C_PANEL, radius=10):
    with widget.canvas.before:
        Color(*color)
        rect = RoundedRectangle(radius=[dp(radius)])
    def _upd(w, v, r=rect, attr="pos"):
        setattr(r, attr, v)
    widget.bind(pos=lambda w,v: _upd(w,v,"pos"), size=lambda w,v: _upd(w,v,"size"))

def toast(msg, dur=2.5):
    lbl_w = Label(text=msg, font_size=sp(13), color=[1,1,1,1], halign="center")
    lbl_w.texture_update()
    w = min(lbl_w.texture_size[0] + dp(32), Window.width - dp(32))
    h = lbl_w.texture_size[1] + dp(24)
    p = Popup(content=lbl_w, size_hint=(None,None), size=(w,h),
              pos_hint={"center_x":.5,"y":.07},
              background="", background_color=[.1,.15,.25,.95],
              separator_height=0, title="", title_size=0)
    p.open()
    Clock.schedule_once(lambda dt: p.dismiss(), dur)

def confirm_popup(title, msg, on_yes):
    content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
    content.add_widget(lbl(msg, size=13, color=C_TEXT, halign="center", h=60))
    row = BoxLayout(spacing=dp(8), size_hint=(1,None), height=dp(44))
    p = Popup(title=title, content=content, size_hint=(.85,None), height=dp(180),
              background="", background_color=[.12,.16,.28,.97],
              title_color=C_TEXT, separator_color=C_PRIMARY)
    yes = btn("확인", bg=C_WARN)
    no  = btn("취소", bg=C_PANEL)
    yes.bind(on_press=lambda _: [p.dismiss(), on_yes()])
    no.bind(on_press=p.dismiss)
    row.add_widget(yes); row.add_widget(no)
    content.add_widget(row)
    p.open()


# ════════════════════════════════════════════════════════════════════
# 뱃지 그리드
# ════════════════════════════════════════════════════════════════════
class BadgeGrid(ScrollView):
    def __init__(self, on_long_press=None, **kw):
        super().__init__(do_scroll_x=False, **kw)
        self.on_long_press = on_long_press
        self._grid = GridLayout(cols=5, spacing=dp(8), padding=dp(10),
                                size_hint_y=None)
        self._grid.bind(minimum_height=self._grid.setter("height"))
        self.add_widget(self._grid)

    def set_items(self, items):
        # items: [(display, tag_code, bg_hex, fg_hex), ...]
        self._grid.clear_widgets()
        if not items:
            self._grid.add_widget(
                lbl("항목 없음", size=13, color=C_SUB, halign="center", h=60))
            return
        for display, tag_code, bg_hex, fg_hex in items:
            b = Button(
                text=display, font_size=sp(12), bold=True,
                background_normal="",
                background_color=get_color_from_hex(bg_hex),
                color=get_color_from_hex(fg_hex),
                size_hint_y=None, height=dp(48),
            )
            b.bind(on_press=partial(self._on_press, tag_code, display))
            self._grid.add_widget(b)

    def _on_press(self, tag_code, display, *_):
        if self.on_long_press:
            self.on_long_press(tag_code, display)


# ════════════════════════════════════════════════════════════════════
# 스캔 화면
# ════════════════════════════════════════════════════════════════════
class ScanScreen(Screen):
    def __init__(self, db: Database, **kw):
        super().__init__(**kw)
        self.db = db
        self._nfc_on = False
        self._build()
        self._refresh_counts()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        # ── 스캔 영역 ──
        scan_box = BoxLayout(orientation="vertical", spacing=dp(10),
                             padding=[dp(14),dp(12)],
                             size_hint=(1,None), height=dp(220))
        panel_bg(scan_box)

        # 결과 표시
        res_wrap = BoxLayout(size_hint=(1,None), height=dp(72),
                             padding=[dp(8),dp(6)])
        panel_bg(res_wrap, color=C_INPUT, radius=12)
        self.result_lbl = Label(
            text="대기 중...", font_size=sp(18), bold=True,
            color=C_SUB, halign="center", valign="middle")
        self.result_lbl.bind(size=self.result_lbl.setter("text_size"))
        res_wrap.add_widget(self.result_lbl)

        # NFC 버튼
        self.nfc_btn = btn("📡  NFC 태그 시작", bg=C_PRIMARY, h=52, fs=16,
                           on_press=self._toggle_nfc)

        # HID 입력
        self.hid_inp = inp("HID 모드: 입력 후 Enter")
        self.hid_inp.bind(on_text_validate=self._hid_scan)

        scan_box.add_widget(res_wrap)
        scan_box.add_widget(self.nfc_btn)
        scan_box.add_widget(self.hid_inp)

        # ── 카운트 ──
        cnt_box = GridLayout(cols=4, spacing=dp(8),
                              padding=[dp(12),dp(8)],
                              size_hint=(1,None), height=dp(80))
        self._cnt_lbls = {}
        for key, title, color in [
            ("total",    "전체",    C_TEXT),
            ("checked",  "반납확인", C_OK),
            ("unchecked","미확인",  C_WARN),
            ("lost",     "분실",    C_LOST),
        ]:
            box = BoxLayout(orientation="vertical", padding=[dp(4),dp(4)])
            panel_bg(box, radius=10)
            n = lbl("0", size=22, color=color, bold=True, halign="center")
            t = lbl(title, size=10, color=C_SUB, halign="center")
            box.add_widget(n); box.add_widget(t)
            cnt_box.add_widget(box)
            self._cnt_lbls[key] = n

        root.add_widget(scan_box)
        root.add_widget(cnt_box)
        root.add_widget(Widget())
        self.add_widget(root)

    def _refresh_counts(self):
        total, checked, unchecked, lost = self.db.get_counts()
        self._cnt_lbls["total"].text    = str(total)
        self._cnt_lbls["checked"].text  = str(checked)
        self._cnt_lbls["unchecked"].text= str(unchecked)
        self._cnt_lbls["lost"].text     = str(lost)

    def _hid_scan(self, widget):
        val = widget.text.strip(); widget.text = ""
        if val: self._process(val)

    def _process(self, tag_code):
        result, dn, cn, lb = self.db.mark_checked(tag_code)
        show = dn or lb or tag_code
        if result == "ok":
            self._show(f"✓  {show}\n반납 확인됨", C_OK)
        elif result == "duplicate":
            self._show(f"⚠  {show}\n이미 확인된 팔찌", C_DUP)
        elif result == "lost":
            self._show(f"⚠  {show}\n분실 처리된 팔찌", C_LOST)
        else:
            self._show(f"✕  {tag_code}\n미등록 팔찌", C_WARN)
        self._refresh_counts()
        # 현황 화면도 갱신 예약
        app = App.get_running_app()
        if app.sm.current == "status":
            app.screens["status"]._load()

    def _show(self, text, color):
        self.result_lbl.text  = text
        self.result_lbl.color = color

    def on_enter(self):
        self._refresh_counts()

    # ── NFC ────────────────────────────────────────────────────
    def _toggle_nfc(self, *_):
        if not ANDROID:
            toast("Android 기기에서만 NFC를 사용할 수 있습니다."); return
        if self._nfc_on: self._stop_nfc()
        else:            self._start_nfc()

    def _start_nfc(self):
        try:
            ctx = PythonActivity.mActivity
            adapter = NfcAdapter.getDefaultAdapter(ctx)
            if not adapter:
                toast("NFC를 지원하지 않는 기기입니다."); return
            if not adapter.isEnabled():
                toast("설정에서 NFC를 켜주세요."); return
            intent = Intent(ctx, ctx.getClass())
            intent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
            pi = PendingIntent.getActivity(
                ctx, 0, intent,
                PendingIntent.FLAG_MUTABLE | PendingIntent.FLAG_UPDATE_CURRENT)
            f = IntentFilter(NfcAdapter.ACTION_TAG_DISCOVERED)
            adapter.enableForegroundDispatch(ctx, pi, [f], None)
            activity.bind(on_new_intent=self._on_intent)
            self._nfc_on = True
            self.nfc_btn.text = "⏹  NFC 중지"
            self.nfc_btn.background_color = C_WARN
            self._show("카드를 폰 뒷면에\n갖다 대세요", C_PRIMARY)
        except Exception as e:
            toast(f"NFC 오류: {e}")

    def _stop_nfc(self):
        try:
            ctx = PythonActivity.mActivity
            NfcAdapter.getDefaultAdapter(ctx).disableForegroundDispatch(ctx)
            activity.unbind(on_new_intent=self._on_intent)
        except Exception: pass
        self._nfc_on = False
        self.nfc_btn.text = "📡  NFC 태그 시작"
        self.nfc_btn.background_color = C_PRIMARY

    def _on_intent(self, intent):
        if intent.getAction() in (
            NfcAdapter.ACTION_TAG_DISCOVERED,
            NfcAdapter.ACTION_NDEF_DISCOVERED,
            NfcAdapter.ACTION_TECH_DISCOVERED,
        ):
            tag = cast(Tag, intent.getParcelableExtra(NfcAdapter.EXTRA_TAG))
            uid = "".join(f"{b & 0xFF:02X}" for b in tag.getId())
            Clock.schedule_once(lambda dt: self._process(uid), 0)

    def on_leave(self):
        if self._nfc_on: self._stop_nfc()


# ════════════════════════════════════════════════════════════════════
# 현황 화면
# ════════════════════════════════════════════════════════════════════
class StatusScreen(Screen):
    def __init__(self, db: Database, **kw):
        super().__init__(**kw)
        self.db  = db
        self._tab = "unchecked"
        self._all = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")

        # 탭 버튼
        tab_row = BoxLayout(size_hint=(1,None), height=dp(46), spacing=dp(1))
        self._tab_btns = {}
        for key, label, color in [
            ("unchecked","미반납", C_WARN),
            ("checked",  "반납완료",C_OK),
            ("lost",     "분실",   C_LOST),
        ]:
            b = Button(text=label, font_size=sp(13), bold=True,
                       background_normal="",
                       background_color=color if key=="unchecked" else C_PANEL,
                       color=C_TEXT)
            b.bind(on_press=partial(self._switch, key))
            tab_row.add_widget(b)
            self._tab_btns[key] = (b, color)

        self._cnt_lbl = lbl("", size=12, color=C_SUB, h=28,
                             padding=[dp(10),0])

        self._grid = BadgeGrid(on_long_press=self._on_badge, size_hint=(1,1))

        root.add_widget(tab_row)
        root.add_widget(self._cnt_lbl)
        root.add_widget(self._grid)
        self.add_widget(root)

    def on_enter(self): self._load()

    def _load(self):
        self._all = self.db.get_all()
        self._render()

    def _switch(self, key, *_):
        self._tab = key
        for k, (b, c) in self._tab_btns.items():
            b.background_color = c if k == key else C_PANEL
        self._render()

    def _render(self):
        cmap = self.db.color_map()
        def_bg = {"unchecked":"#ef4444","checked":"#22c55e","lost":"#a855f7"}
        items_data = [b for b in self._all if b["status"] == self._tab]
        tab_lbl = {"unchecked":"미반납","checked":"반납완료","lost":"분실"}
        self._cnt_lbl.text = f"  {len(items_data)}개 {tab_lbl.get(self._tab,'')}"

        items = []
        for b in items_data:
            label = b["display_number"] or b["tag_code"]
            if self._tab == "lost":
                bg, fg = "#a855f7", "#ffffff"
            else:
                cn = b["color_name"]
                bg, fg = cmap.get(cn, (def_bg[self._tab], "#ffffff")) if cn else (def_bg[self._tab], "#ffffff")
            items.append((label, b["tag_code"], bg, fg))
        self._grid.set_items(items)

    def _on_badge(self, tag_code, display):
        tab = self._tab
        actions = []
        if tab == "unchecked":
            actions = [("✓  반납 처리",      "checked", C_OK),
                       ("⚠  분실 처리",      "lost",    C_LOST)]
        elif tab == "checked":
            actions = [("↩  미반납으로",     "unchecked", C_DUP),
                       ("⚠  분실 처리",      "lost",      C_LOST)]
        elif tab == "lost":
            actions = [("↩  미반납으로 복구","unchecked", C_DUP)]

        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        popup = Popup(title=display, title_color=C_TEXT, title_size=sp(15),
                      separator_color=C_PRIMARY, background="",
                      background_color=[.12,.16,.28,.97],
                      size_hint=(.82,None), height=dp(60+54*len(actions)))
        for a_lbl, new_status, color in actions:
            b = btn(a_lbl, bg=color, h=46)
            def _do(_, tc=tag_code, st=new_status, p=popup):
                p.dismiss()
                self.db.set_status(tc, st)
                self._load()
                App.get_running_app().screens["scan"]._refresh_counts()
            b.bind(on_press=_do)
            content.add_widget(b)
        popup.content = content
        popup.open()


# ════════════════════════════════════════════════════════════════════
# 관리 화면
# ════════════════════════════════════════════════════════════════════
class ManageScreen(Screen):
    def __init__(self, db: Database, **kw):
        super().__init__(**kw)
        self.db = db
        self._nfc_reg_on = False
        self._build()

    def _build(self):
        sv = ScrollView(do_scroll_x=False)
        root = BoxLayout(orientation="vertical", spacing=dp(10),
                         padding=dp(12), size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        # ── 등록 폼 ──
        root.add_widget(lbl("팔찌 등록", size=14, bold=True, color=C_SUB))
        self._inp_dn    = inp("표시 번호 (예: 101)")
        self._inp_tag   = inp("태그 코드 (HEX)")
        self._inp_label = inp("비고 (선택)")
        self._color_sp  = Spinner(
            text="색상 없음", values=["색상 없음"],
            background_normal="", background_color=C_PANEL,
            color=C_TEXT, font_size=sp(13),
            size_hint=(1,None), height=dp(44))

        self._nfc_reg_btn = btn("📡  NFC로 태그 코드 읽기", bg=C_PRIMARY, h=48,
                                on_press=self._toggle_nfc_reg)

        for w in [self._inp_dn, self._inp_tag, self._color_sp,
                  self._inp_label, self._nfc_reg_btn,
                  btn("등록", bg=C_OK, h=48, on_press=self._add)]:
            root.add_widget(w)

        # ── 마감 초기화 ──
        root.add_widget(Widget(size_hint=(1,None), height=dp(6)))
        root.add_widget(btn("마감 초기화 (분실 제외)", bg=C_WARN, h=48,
                            on_press=self._reset))

        # ── 목록 ──
        root.add_widget(Widget(size_hint=(1,None), height=dp(6)))
        root.add_widget(lbl("등록된 팔찌", size=14, bold=True, color=C_SUB))
        self._list_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                    size_hint=(1,None))
        self._list_box.bind(minimum_height=self._list_box.setter("height"))
        root.add_widget(self._list_box)

        sv.add_widget(root)
        self.add_widget(sv)

    def on_enter(self):
        self._refresh_colors()
        self._refresh_list()

    def _refresh_colors(self):
        names = ["색상 없음"] + [c["name"] for c in self.db.get_colors()]
        self._color_sp.values = names

    def _add(self, *_):
        tag = self._inp_tag.text.strip()
        if not tag: toast("태그 코드를 입력하세요."); return
        ok, msg = self.db.add_bracelet(
            tag,
            self._inp_dn.text.strip(),
            self._color_sp.text if self._color_sp.text != "색상 없음" else "",
            self._inp_label.text.strip())
        toast(msg)
        if ok:
            self._inp_dn.text = self._inp_tag.text = self._inp_label.text = ""
            self._color_sp.text = "색상 없음"
            self._refresh_list()
            App.get_running_app().screens["scan"]._refresh_counts()

    def _reset(self, *_):
        confirm_popup("마감 초기화",
                      "모든 팔찌를 미확인으로 초기화합니다.\n분실은 유지됩니다.",
                      lambda: [self.db.reset_all(),
                               self._refresh_list(),
                               App.get_running_app().screens["scan"]._refresh_counts(),
                               toast("초기화되었습니다.")])

    def _refresh_list(self):
        self._list_box.clear_widgets()
        cmap = self.db.color_map()
        st_t = {"unchecked":"미확인","checked":"반납확인","lost":"분실"}
        st_c = {"unchecked":C_WARN,"checked":C_OK,"lost":C_LOST}
        for b in self.db.get_all():
            row = BoxLayout(spacing=dp(8), size_hint=(1,None), height=dp(54),
                            padding=[dp(10),dp(6)])
            panel_bg(row, radius=10)
            cn = b["color_name"]
            dot_hex = cmap.get(cn, ("#334155","#fff"))[0] if cn else "#334155"
            dot = Widget(size_hint=(None,None), size=(dp(12),dp(12)))
            with dot.canvas:
                Color(*get_color_from_hex(dot_hex))
                Ellipse(size=dot.size, pos=dot.pos)
            info = BoxLayout(orientation="vertical")
            info.add_widget(lbl(b["display_number"] or b["tag_code"], size=14, bold=True))
            info.add_widget(lbl(b["tag_code"], size=10, color=C_SUB))
            st = b["status"]
            st_lbl = lbl(st_t.get(st,st), size=11, color=st_c.get(st,C_SUB),
                         halign="right", size_hint_x=None, width=dp(60))
            del_btn = btn("삭제", bg=C_PANEL, fg=list(C_WARN),
                          h=34, fs=12, size_hint_x=None, width=dp(48))
            del_btn.bind(on_press=partial(self._delete, b["id"]))
            row.add_widget(dot); row.add_widget(info)
            row.add_widget(st_lbl); row.add_widget(del_btn)
            self._list_box.add_widget(row)

    def _delete(self, bid, *_):
        self.db.delete_bracelet(bid)
        self._refresh_list()
        App.get_running_app().screens["scan"]._refresh_counts()
        toast("삭제되었습니다.")

    # ── NFC 등록용 ──────────────────────────────────────────────
    def _toggle_nfc_reg(self, *_):
        if not ANDROID:
            toast("Android 기기에서만 NFC를 사용할 수 있습니다."); return
        if self._nfc_reg_on: self._stop_nfc_reg()
        else:                self._start_nfc_reg()

    def _start_nfc_reg(self):
        try:
            ctx = PythonActivity.mActivity
            adapter = NfcAdapter.getDefaultAdapter(ctx)
            if not adapter or not adapter.isEnabled():
                toast("NFC를 켜주세요."); return
            intent = Intent(ctx, ctx.getClass())
            intent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
            pi = PendingIntent.getActivity(
                ctx, 0, intent,
                PendingIntent.FLAG_MUTABLE | PendingIntent.FLAG_UPDATE_CURRENT)
            adapter.enableForegroundDispatch(
                ctx, pi, [IntentFilter(NfcAdapter.ACTION_TAG_DISCOVERED)], None)
            activity.bind(on_new_intent=self._on_reg_intent)
            self._nfc_reg_on = True
            self._nfc_reg_btn.text = "⏹  중지"
            self._nfc_reg_btn.background_color = C_WARN
            toast("팔찌를 갖다 대세요...")
        except Exception as e:
            toast(f"NFC 오류: {e}")

    def _stop_nfc_reg(self):
        try:
            ctx = PythonActivity.mActivity
            NfcAdapter.getDefaultAdapter(ctx).disableForegroundDispatch(ctx)
            activity.unbind(on_new_intent=self._on_reg_intent)
        except Exception: pass
        self._nfc_reg_on = False
        self._nfc_reg_btn.text = "📡  NFC로 태그 코드 읽기"
        self._nfc_reg_btn.background_color = C_PRIMARY

    def _on_reg_intent(self, intent):
        if intent.getAction() in (NfcAdapter.ACTION_TAG_DISCOVERED,
                                   NfcAdapter.ACTION_NDEF_DISCOVERED,
                                   NfcAdapter.ACTION_TECH_DISCOVERED):
            tag = cast(Tag, intent.getParcelableExtra(NfcAdapter.EXTRA_TAG))
            uid = "".join(f"{b & 0xFF:02X}" for b in tag.getId())
            Clock.schedule_once(lambda dt: self._on_uid(uid), 0)
            self._stop_nfc_reg()

    def _on_uid(self, uid):
        self._inp_tag.text = uid
        toast(f"UID 읽음: {uid}")

    def on_leave(self):
        if self._nfc_reg_on: self._stop_nfc_reg()


# ════════════════════════════════════════════════════════════════════
# 색상 관리 화면
# ════════════════════════════════════════════════════════════════════
class ColorScreen(Screen):
    def __init__(self, db: Database, **kw):
        super().__init__(**kw)
        self.db = db
        self._bg = "#3b82f6"
        self._fg = "#ffffff"
        self._build()

    def _build(self):
        sv = ScrollView(do_scroll_x=False)
        root = BoxLayout(orientation="vertical", spacing=dp(10),
                         padding=dp(12), size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        root.add_widget(lbl("색상 추가", size=14, bold=True, color=C_SUB))
        self._inp_name = inp("색상 이름 (예: 핑크)")

        # 색상 선택 버튼들
        clr_row = BoxLayout(spacing=dp(8), size_hint=(1,None), height=dp(44))
        self._bg_btn = btn("배경색", bg=get_color_from_hex(self._bg), h=44,
                           on_press=lambda _: self._pick("bg"))
        self._fg_btn = btn("글자색", bg=get_color_from_hex(self._fg),
                           fg=[0,0,0,1], h=44,
                           on_press=lambda _: self._pick("fg"))
        self._prev   = btn("미리보기", bg=get_color_from_hex(self._bg),
                           fg=get_color_from_hex(self._fg), h=44)
        clr_row.add_widget(self._bg_btn)
        clr_row.add_widget(self._fg_btn)
        clr_row.add_widget(self._prev)

        root.add_widget(self._inp_name)
        root.add_widget(clr_row)
        root.add_widget(btn("추가", bg=C_PRIMARY, h=48, on_press=self._add))

        root.add_widget(Widget(size_hint=(1,None), height=dp(6)))
        root.add_widget(lbl("색상 목록", size=14, bold=True, color=C_SUB))
        self._list = BoxLayout(orientation="vertical", spacing=dp(6),
                                size_hint=(1,None))
        self._list.bind(minimum_height=self._list.setter("height"))
        root.add_widget(self._list)

        sv.add_widget(root)
        self.add_widget(sv)

    def on_enter(self): self._refresh()

    def _pick(self, which):
        cp = ColorPicker()
        popup = Popup(title="색상 선택", content=cp,
                      size_hint=(.95,.85),
                      background="", background_color=[.12,.16,.28,.97],
                      title_color=C_TEXT, separator_color=C_PRIMARY)
        def _on_select(*_):
            rgba = cp.color
            hex_val = "#{:02X}{:02X}{:02X}".format(
                int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))
            if which == "bg":
                self._bg = hex_val
                self._bg_btn.background_color = get_color_from_hex(hex_val)
            else:
                self._fg = hex_val
                self._fg_btn.background_color = get_color_from_hex(hex_val)
            self._prev.background_color = get_color_from_hex(self._bg)
            self._prev.color            = get_color_from_hex(self._fg)
            popup.dismiss()
        cp.bind(color=lambda w,v: None)
        ok = btn("선택", bg=C_PRIMARY, h=44, on_press=_on_select)
        wrapper = BoxLayout(orientation="vertical")
        wrapper.add_widget(cp)
        wrapper.add_widget(ok)
        popup.content = wrapper
        popup.open()

    def _add(self, *_):
        name = self._inp_name.text.strip()
        if not name: toast("색상 이름을 입력하세요."); return
        ok, msg = self.db.add_color(name, self._bg, self._fg)
        toast(msg)
        if ok:
            self._inp_name.text = ""
            self._refresh()
            App.get_running_app().screens["manage"]._refresh_colors()

    def _refresh(self):
        self._list.clear_widgets()
        for c in self.db.get_colors():
            row = BoxLayout(spacing=dp(8), size_hint=(1,None), height=dp(48),
                            padding=[dp(8),dp(4)])
            panel_bg(row, radius=8)
            swatch = Widget(size_hint=(None,None), size=(dp(36),dp(36)))
            with swatch.canvas:
                Color(*get_color_from_hex(c["bg"]))
                RoundedRectangle(size=swatch.size, pos=swatch.pos, radius=[dp(6)])
                Color(*get_color_from_hex(c["fg"]))
            nm = lbl(c["name"], size=14, color=C_TEXT)
            bg_lbl = lbl(c["bg"], size=11, color=C_SUB, halign="right",
                         size_hint_x=None, width=dp(72))
            del_b = btn("삭제", bg=C_PANEL, fg=list(C_WARN),
                        h=34, fs=12, size_hint_x=None, width=dp(48))
            del_b.bind(on_press=partial(self._delete, c["name"]))
            row.add_widget(swatch); row.add_widget(nm)
            row.add_widget(bg_lbl); row.add_widget(del_b)
            self._list.add_widget(row)

    def _delete(self, name, *_):
        self.db.delete_color(name)
        self._refresh()
        App.get_running_app().screens["manage"]._refresh_colors()
        toast(f"'{name}' 삭제됨")


# ════════════════════════════════════════════════════════════════════
# 앱 메인
# ════════════════════════════════════════════════════════════════════
class RFIDApp(App):
    def build(self):
        if ANDROID:
            request_permissions([Permission.NFC])

        self.db = Database(DB_PATH)

        root = BoxLayout(orientation="vertical")

        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        self.screens = {
            "scan":    ScanScreen(self.db,    name="scan"),
            "status":  StatusScreen(self.db,  name="status"),
            "manage":  ManageScreen(self.db,  name="manage"),
            "colors":  ColorScreen(self.db,   name="colors"),
        }
        for s in self.screens.values():
            self.sm.add_widget(s)

        # 하단 탭 바
        nav = BoxLayout(size_hint=(1,None), height=dp(56))
        with nav.canvas.before:
            Color(*C_PANEL)
            self._nav_rect = Rectangle(size=nav.size, pos=nav.pos)
        nav.bind(
            size=lambda w,v: setattr(self._nav_rect,"size",v),
            pos= lambda w,v: setattr(self._nav_rect,"pos", v))

        self._nav_btns = {}
        for key, label in [("scan","📡\n스캔"),("status","📋\n현황"),
                            ("manage","⚙\n관리"),("colors","🎨\n색상")]:
            b = Button(
                text=label, font_size=sp(11),
                background_normal="",
                background_color=C_PRIMARY if key=="scan" else C_PANEL,
                color=C_TEXT, halign="center")
            b.bind(on_press=partial(self._switch, key))
            nav.add_widget(b)
            self._nav_btns[key] = b

        root.add_widget(self.sm)
        root.add_widget(nav)
        return root

    def _switch(self, key, *_):
        self.sm.current = key
        for k, b in self._nav_btns.items():
            b.background_color = C_PRIMARY if k == key else C_PANEL

    def get_application_name(self):
        return "팔찌 반납 확인"


if __name__ == "__main__":
    RFIDApp().run()
