import ctypes
import math
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
from time import perf_counter

import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox

# ============================================================
# NEXUS 4.0 · fun edition - Disk Analyzer
# Требуется: pip install customtkinter
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT = "Segoe UI"

BG = "#0C0C10"
PANEL = "#15151C"
PANEL2 = "#1E1E28"
HOVER = "#2A2A38"
ACCENT = "#B8F55B"
ACCENT_HOVER = "#9ED944"
TEXT = "#ECECF1"
MUTED = "#7C7C8A"
DARK = "#0C0C10"
WARN = "#FFB454"
BAD = "#FF6B6B"
BAD_DARK = "#3A1D22"
PINK = "#FF8AD8"
CYAN = "#5BE8F5"

ARCHIVES = (
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".bz2", ".xz", ".iso", ".cab", ".jar",
    ".tgz", ".wim"
)

ICONS = {"ПАПКА": "📁", "АРХИВ": "📦", "ФАЙЛ": "📄"}

BUSY_QUIPS = [
    "Пересчитываю байтики по одному...",
    "Заглядываю под каждый ковёр...",
    "Взвешиваю папки на кухонных весах...",
    "Ищу, кто сожрал всё место...",
    "Спрашиваю файлы, сколько они весят...",
    "Слегка паникую, но считаю...",
    "Тихо шуршу по папкам...",
    "Это быстрее, чем кажется. Почти.",
]

DONE_QUIPS = [
    "Готово! Можешь выдохнуть.",
    "Сделано. Я молодец, ты тоже.",
    "Всё взвешено и измерено ✨",
    "Ну вот, а ты боялся.",
]

MASCOT_JOKES = [
    "Ой! Щекотно 😆",
    "Диск не резиновый, но я стараюсь.",
    "Удалять «потом» — не мужское занятие.",
    "Мой создатель Арсений — король.",
    "Я не ем байты. Я их только считаю.",
    "Я сегодня не выспался. Это факт.",
    "Корзину ты тоже чистить не будешь, да?",
    "Не нажимай так часто, я краснею.",
    "НЕ ТРОГАЙ!!! УБЬЕТ!!",
    "Мне очень приятно :)",
    "Позовите Арсения, он знает что делать!",
]

EMPTY_QUIPS = [
    "Тут пусто, как в холодильнике перед зарплатой 🕳️\nВыбери папку",
    "Ни одного файла. Подозрительно тихо 🦗\nВыбери папку",
    "Пока что я считаю воздух 🌬️\nВыбери папку",
]

SIDEBAR_QUIPS = [
    "версия без паники",
    "ни один байт не пострадал",
    "работает на честном слове",
]


def format_size(size):
    """Return a readable file size."""
    if size is None:
        return "Считается..."
    if size >= 1024 ** 4:
        return f"{size / (1024 ** 4):.2f} TB"
    if size >= 1024 ** 3:
        return f"{size / (1024 ** 3):.2f} GB"
    if size >= 1024 ** 2:
        return f"{size / (1024 ** 2):.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size} B"


def size_animal(size):
    """Fun 'weight class' for a size."""
    if size is None:
        return "⏳"
    if size < 1024 ** 2:
        return "🐜"
    if size < 50 * 1024 ** 2:
        return "🐁"
    if size < 500 * 1024 ** 2:
        return "🐈"
    if size < 5 * 1024 ** 3:
        return "🐘"
    return "🦖"


def size_tag(size):
    if size is None:
        return ()
    if size >= 10 * 1024 ** 3:
        return ("huge",)
    if size >= 1024 ** 3:
        return ("big",)
    return ()


def size_text(size):
    if size is None:
        return "⏳ считается..."
    return f"{format_size(size)}   {size_animal(size)}"


def size_quip(total):
    if total < 1024 ** 2:
        return "Лёгкое как пёрышко 🪶"
    if total < 100 * 1024 ** 2:
        return "Вполне прилично 🙂"
    if total < 1024 ** 3:
        return "Уже ощутимо 🏋️"
    if total < 10 * 1024 ** 3:
        return "Тут кто-то хорошо поселился 🐘"
    return "Это не папка, это государство 🦖"


def get_folder_size(folder, should_stop=None):
    """
    Calculate the total size of a folder recursively (iterative scandir).
    Symlinks are skipped to avoid loops and double traversal.
    """
    total = 0
    counter = 0
    stack = [folder]

    while stack:
        if should_stop and should_stop():
            return total
        current = stack.pop()
        try:
            with os.scandir(current) as iterator:
                for entry in iterator:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(
                                follow_symlinks=False
                            ).st_size
                    except OSError:
                        pass

                    counter += 1
                    if counter % 800 == 0:
                        # Give the UI thread a chance to draw frames.
                        time.sleep(0.0005)
        except OSError:
            pass

    return total


IS_WIN = sys.platform.startswith("win")


def lerp_color(a, b, k):
    """Плавный переход между двумя hex-цветами (k от 0 до 1)."""
    k = max(0.0, min(1.0, k))
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(
        "%02x" % int(
            int(a[i:i + 2], 16)
            + (int(b[i:i + 2], 16) - int(a[i:i + 2], 16)) * k
        )
        for i in (0, 2, 4)
    )


class _SHQUERYRBINFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("wFunc", ctypes.c_uint),
        ("pFrom", ctypes.c_wchar_p),
        ("pTo", ctypes.c_wchar_p),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", ctypes.c_int),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_wchar_p),
    ]


def trash_dirs():
    """Папки корзины для Linux/macOS: (files, info или None)."""
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, ".Trash"), None
    base = (
        os.environ.get("XDG_DATA_HOME")
        or os.path.join(home, ".local", "share")
    )
    return (
        os.path.join(base, "Trash", "files"),
        os.path.join(base, "Trash", "info"),
    )


def recycle_info():
    """Возвращает (размер, число объектов) корзины."""
    if IS_WIN:
        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(
            None, ctypes.byref(info)
        )
        if res != 0:
            raise OSError(f"SHQueryRecycleBin: {res & 0xFFFFFFFF:#x}")
        return int(info.i64Size), int(info.i64NumItems)

    files_dir = trash_dirs()[0]
    if not os.path.isdir(files_dir):
        return 0, 0
    size = count = 0
    with os.scandir(files_dir) as it:
        for entry in it:
            count += 1
            try:
                if entry.is_dir(follow_symlinks=False):
                    size += get_folder_size(entry.path)
                else:
                    size += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
    return size, count


def empty_recycle():
    """Очищает корзину без системных диалогов."""
    if IS_WIN:
        # 0x7 = без подтверждения, без окна прогресса, без звука
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
        if res != 0:
            try:
                if recycle_info()[1] == 0:
                    return  # уже пусто — система вернула «ошибку»
            except OSError:
                pass
            raise OSError(
                f"Не удалось очистить корзину (код {res & 0xFFFFFFFF:#x})"
            )
        return

    for folder in trash_dirs():
        if not folder or not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass


def move_to_trash(path):
    """Отправляет файл или папку в корзину (без сторонних библиотек)."""
    path = os.path.abspath(path)

    if IS_WIN:
        op = _SHFILEOPSTRUCTW()
        op.wFunc = 3  # FO_DELETE
        op.pFrom = path + "\0"  # список путей заканчивается двойным \0
        # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI
        op.fFlags = 0x40 | 0x10 | 0x4 | 0x400
        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if res != 0:
            raise OSError(f"Проводник вернул код {res:#x}")
        if op.fAnyOperationsAborted:
            raise OSError("Операция прервана")
        return

    try:
        from send2trash import send2trash
        send2trash(path)
        return
    except ImportError:
        pass

    files_dir, info_dir = trash_dirs()
    os.makedirs(files_dir, exist_ok=True)
    base = os.path.basename(path.rstrip(os.sep)) or "item"
    stem, ext = os.path.splitext(base)
    name, n = base, 1
    while os.path.lexists(os.path.join(files_dir, name)):
        name = f"{stem}.{n}{ext}"
        n += 1
    if info_dir:
        from urllib.parse import quote
        os.makedirs(info_dir, exist_ok=True)
        with open(
            os.path.join(info_dir, name + ".trashinfo"), "w",
            encoding="utf-8"
        ) as f:
            f.write(
                "[Trash Info]\nPath=" + quote(path)
                + "\nDeletionDate=" + time.strftime("%Y-%m-%dT%H:%M:%S")
                + "\n"
            )
    shutil.move(path, os.path.join(files_dir, name))


class Nexus(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("y0m files | Disk Analyzer")
        self.geometry("1280x800")
        self.minsize(980, 700)
        self.configure(fg_color=BG)

        # Плавное появление окна
        try:
            self.attributes("-alpha", 0.0)
            self.after(30, self.fade_in)
        except Exception:
            pass

        # Кэш размеров для Tree Explorer: путь -> список элементов
        self.tree_cache = {}

        # Анимированные счётчики карточек
        self.card_tgt = [0, 0, 0, 0]
        self.card_cur = [0.0, 0.0, 0.0, 0.0]
        self.card_txt = ["", "", "", ""]
        self.next_blink = perf_counter() + 2.5
        self.blink_end = 0.0

        # Сортировка таблицы и данные строк
        self.sort_col = "size"
        self.sort_rev = True
        self.row_data = {}

        # Плавная анимация (фаза копится, скорость меняется плавно)
        self.last_frame = perf_counter()
        self.bob_phase = 0.0
        self.bob_speed = 2.2
        self.bob_amp = 2.0
        self.look_phase = 0.0
        self.look_speed = 1.3
        self._type_token = 0

        self.mode = "Tree Explorer"
        self.current_path = ""
        self.history = []
        self.items = []
        self.item_by_path = {}
        self.row_ids = {}
        self.full_results = []
        self.events = queue.Queue()
        self.worker_running = False
        self.scan_token = 0
        self._polling = False
        self._search_job = None

        # Animation state
        self.t0 = perf_counter()
        self.jump_start = -10.0
        self.last_dy = 0.0
        self.last_dx = 0.0
        self.bar_mode = "idle"      # idle | indet | det
        self.bar_l = 0.0            # левый край заливки (доля 0..1)
        self.bar_r = 0.0            # правый край заливки (доля 0..1)
        self.bar_target = 0.0
        self._bar_locked = False    # indet: блок следует за целью без лага
        self.next_quip = 0.0

        # Эффекты, уведомления, корзина
        self.particles = []
        self.card_frames = []
        self.card_hover = [0.0, 0.0, 0.0, 0.0]
        self.toast_t0 = 0.0
        self.toast_hold = 2.4
        self._pulse_col = None
        self._pulsing = False
        self._hover_row = None
        self.deleting = False
        self.trash_busy = False
        self.trash_info = None

        # Плавная смена размера окна
        self._win_anim = None
        self._zoomed_small = None
        self._resizing_until = 0.0

        self.create_interface()
        self.bind("<Configure>", self.on_window_configure)
        self.bind("<F11>", lambda e: self.toggle_zoom())
        self.set_face("idle")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tick()
        self.after(400, self.refresh_trash_info)

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def create_interface(self):
        self.sidebar = ctk.CTkFrame(
            self, width=220, fg_color=PANEL, corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Mascot
        self.mascot = ctk.CTkCanvas(
            self.sidebar, width=200, height=92,
            bg=PANEL, highlightthickness=0, cursor="hand2"
        )
        self.mascot.pack(pady=(16, 0))
        self.mascot.create_oval(
            22, 76, 62, 82, fill=PANEL2, outline=""
        )
        self.mascot.create_oval(
            10, 14, 74, 74, fill=ACCENT, outline="", tags=("m",)
        )
        for x in (26, 46):
            self.mascot.create_oval(
                x, 32, x + 14, 48, fill="white", outline="",
                tags=("m", "eye")
            )
        for x in (30, 50):
            self.mascot.create_oval(
                x, 37, x + 6, 43, fill=DARK, outline="",
                tags=("m", "pupil")
            )
        self.mouth = None
        self.mascot.move("all", 58, 8)  # центрируем маскота
        self.mascot.bind("<Button-1>", self.on_mascot_click)

        ctk.CTkLabel(
            self.sidebar,
            text="y0m files",
            font=(FONT, 26, "bold", "italic"),
            text_color=TEXT
        ).pack(pady=(8, 0))

        self.sidebar_quip = ctk.CTkLabel(
            self.sidebar,
            text=random.choice(SIDEBAR_QUIPS),
            font=(FONT, 11),
            text_color=MUTED
        )
        self.sidebar_quip.pack(pady=(0, 6))

        self.speech = ctk.CTkLabel(
            self.sidebar,
            text="",
            font=(FONT, 11, "italic"),
            text_color=ACCENT,
            wraplength=190,
            height=34
        )
        self.speech.pack(pady=(0, 10))

        ctk.CTkLabel(
            self.sidebar,
            text="РЕЖИМ",
            text_color=MUTED,
            font=(FONT, 10, "bold")
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self.mode_switch = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Tree Explorer", "Full Scan"],
            command=self.change_mode,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=PANEL2,
            unselected_hover_color=HOVER,
            text_color=TEXT,
            font=(FONT, 11)
        )
        self.mode_switch.pack(fill="x", padx=12, pady=(0, 18))
        self.mode_switch.set("Tree Explorer")

        ctk.CTkLabel(
            self.sidebar,
            text="НАВИГАЦИЯ",
            text_color=MUTED,
            font=(FONT, 10, "bold")
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self.nav_button("⌂   Выбрать папку", self.choose_folder)
        self.nav_button("◀   Назад", self.go_back)
        self.nav_button("↑   Уровнем выше", self.go_up)
        self.nav_button("↻   Обновить", self.refresh)

        ctk.CTkLabel(
            self.sidebar,
            text="ДЕЙСТВИЯ",
            text_color=MUTED,
            font=(FONT, 10, "bold")
        ).pack(anchor="w", padx=20, pady=(12, 4))

        self.nav_button(
            "🗑   Удалить выбранное", self.delete_selected, hover=BAD_DARK
        )
        self.nav_button(
            "♻️   Очистить корзину", self.empty_trash, hover=BAD_DARK
        )
        self.trash_label = ctk.CTkLabel(
            self.sidebar,
            text="Корзина: считаю...",
            text_color=MUTED,
            font=(FONT, 10),
            anchor="w"
        )
        self.trash_label.pack(fill="x", padx=22, pady=(2, 0))

        ctk.CTkLabel(
            self.sidebar,
            text="tree explorer — папка за раз.\nfull scan — всё и сразу.",
            text_color=MUTED,
            font=(FONT, 10),
            justify="left"
        ).pack(side="bottom", anchor="w", padx=20, pady=10)

        # Main panel
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(
            side="left", fill="both", expand=True,
            padx=26, pady=22
        )

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))

        self.title_label = ctk.CTkLabel(
            header,
            text="Tree Explorer",
            font=(FONT, 28, "bold"),
            text_color=TEXT
        )
        self.title_label.pack(side="left")

        self.choose_button = ctk.CTkButton(
            header,
            text="＋  Выбрать папку",
            width=170,
            height=40,
            corner_radius=20,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=DARK,
            font=(FONT, 13, "bold"),
            command=self.choose_folder
        )
        self.choose_button.pack(side="right")

        self.path_label = ctk.CTkLabel(
            self.main,
            text="папка не выбрана · диск ждёт приключений",
            text_color=MUTED,
            font=(FONT, 12),
            anchor="w"
        )
        self.path_label.pack(fill="x", pady=(0, 14))

        # Statistic cards
        stats = ctk.CTkFrame(self.main, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 14))

        self.folders_label = self.make_card(stats, "📁  ПАПКИ", "0")
        self.files_label = self.make_card(stats, "📄  ФАЙЛЫ", "0")
        self.archives_label = self.make_card(stats, "📦  АРХИВЫ", "0")
        self.size_label = self.make_card(stats, "⚖️  РАЗМЕР ФАЙЛОВ", "0 B")
        self.card_labels = [
            self.folders_label, self.files_label,
            self.archives_label, self.size_label
        ]

        # Status + animated progress bar
        progress_frame = ctk.CTkFrame(
            self.main, fg_color=PANEL, corner_radius=14
        )
        progress_frame.pack(fill="x", pady=(0, 14))

        status_row = ctk.CTkFrame(progress_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=(10, 6))

        self.status_label = ctk.CTkLabel(
            status_row,
            text="Выбери папку для начала",
            text_color=TEXT,
            font=(FONT, 12),
            anchor="w"
        )
        self.status_label.pack(side="left")

        self.quip_label = ctk.CTkLabel(
            status_row,
            text="",
            text_color=MUTED,
            font=(FONT, 11, "italic"),
            anchor="e"
        )
        self.quip_label.pack(side="right")

        bar_holder = ctk.CTkFrame(
            progress_frame, fg_color=PANEL2, corner_radius=4, height=6
        )
        bar_holder.pack(fill="x", padx=16, pady=(0, 14))
        bar_holder.pack_propagate(False)

        self.bar = ctk.CTkCanvas(
            bar_holder, height=6, bg=PANEL2, highlightthickness=0
        )
        self.bar.pack(fill="both", expand=True)
        self.bar_fill = self.bar.create_rectangle(
            0, 0, 0, 6, fill=ACCENT, outline=""
        )

        # Table header and search
        table_top = ctk.CTkFrame(self.main, fg_color="transparent")
        table_top.pack(fill="x", pady=(0, 9))

        self.table_title = ctk.CTkLabel(
            table_top,
            text="Содержимое текущей папки",
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )
        self.table_title.pack(side="left")

        self.search = ctk.CTkEntry(
            table_top,
            placeholder_text="🔎  Поиск по имени...",
            width=245,
            height=36,
            corner_radius=18,
            fg_color=PANEL,
            border_width=0,
            font=(FONT, 12)
        )
        self.search.pack(side="right")
        self.search.bind("<KeyRelease>", self.on_search_key)

        # Treeview
        table_frame = ctk.CTkFrame(
            self.main, fg_color=PANEL, corner_radius=14
        )
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=PANEL,
            foreground=TEXT,
            fieldbackground=PANEL,
            rowheight=34,
            borderwidth=0,
            font=(FONT, 10)
        )
        style.configure(
            "Treeview.Heading",
            background=PANEL2,
            foreground=MUTED,
            font=(FONT, 9, "bold"),
            relief="flat",
            borderwidth=0
        )
        style.map(
            "Treeview",
            background=[("selected", "#2C3A18")],
            foreground=[("selected", ACCENT)]
        )
        style.map("Treeview.Heading", background=[("active", HOVER)])
        style.configure(
            "Vertical.TScrollbar",
            background=PANEL2,
            troughcolor=PANEL,
            bordercolor=PANEL,
            arrowcolor=MUTED,
            relief="flat"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=("name", "type", "size", "path"),
            show="headings"
        )
        self.heading_names = {
            "name": "ИМЯ", "type": "ТИП",
            "size": "РАЗМЕР", "path": "ПОЛНЫЙ ПУТЬ"
        }
        for col in self.heading_names:
            self.tree.heading(
                col, command=lambda c=col: self.sort_by(c)
            )
        self.update_headings()

        # name и path тянутся вместе с окном, type и size — фиксированные
        self.tree.column("name", width=250, minwidth=160, stretch=True)
        self.tree.column(
            "type", width=95, minwidth=95, anchor="center", stretch=False
        )
        self.tree.column(
            "size", width=150, minwidth=130, anchor="center", stretch=False
        )
        self.tree.column("path", width=500, minwidth=200, stretch=True)

        self.tree.tag_configure("big", foreground=WARN)
        self.tree.tag_configure("huge", foreground=BAD)
        self.tree.tag_configure("hover", background=PANEL2)
        self.tree.tag_configure(
            "dying", background="#4A1F24", foreground=BAD
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(
            side="left", fill="both", expand=True,
            padx=(10, 0), pady=10
        )
        scrollbar.pack(side="right", fill="y", padx=5, pady=10)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", lambda e: self.set_hover(None))
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

        self.empty_label = ctk.CTkLabel(
            table_frame,
            text=random.choice(EMPTY_QUIPS),
            text_color=MUTED,
            fg_color=PANEL,
            font=(FONT, 14),
            justify="center"
        )
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

        # Bottom actions
        bottom = ctk.CTkFrame(self.main, fg_color="transparent")
        bottom.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(
            bottom,
            text="📂  Открыть расположение",
            command=self.open_selected,
            height=42,
            corner_radius=21,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=DARK,
            font=(FONT, 12, "bold")
        ).pack(side="left")

        self.calculate_button = ctk.CTkButton(
            bottom,
            text="📊  Пересчитать размеры",
            command=self.calculate_selected_folder,
            height=42,
            corner_radius=21,
            fg_color=PANEL2,
            hover_color=HOVER,
            text_color=TEXT,
            font=(FONT, 12)
        )
        self.calculate_button.pack(side="left", padx=9)

        self.delete_button = ctk.CTkButton(
            bottom,
            text="🗑  Удалить",
            command=self.delete_selected,
            height=42,
            corner_radius=21,
            fg_color=BAD_DARK,
            hover_color="#5A262D",
            text_color=BAD,
            font=(FONT, 12, "bold")
        )
        self.delete_button.pack(side="left")

        self.bottom_hint = ctk.CTkLabel(
            bottom,
            text="Размеры считаются для папок в этом каталоге",
            text_color=MUTED,
            font=(FONT, 11)
        )
        self.bottom_hint.pack(side="right")

        # Всплывающее уведомление (выезжает справа снизу)
        self.toast = ctk.CTkFrame(
            self, fg_color=PANEL2, corner_radius=14,
            border_width=2, border_color=ACCENT
        )
        self.toast_label = ctk.CTkLabel(
            self.toast, text="", text_color=TEXT,
            font=(FONT, 12, "bold"), wraplength=340, justify="left"
        )
        self.toast_label.pack(padx=18, pady=12)

    def nav_button(self, text, command, hover=PANEL2):
        ctk.CTkButton(
            self.sidebar,
            text=text,
            anchor="w",
            height=34,
            corner_radius=10,
            fg_color="transparent",
            hover_color=hover,
            text_color=TEXT,
            font=(FONT, 12),
            command=command
        ).pack(fill="x", padx=12, pady=2)

    def make_card(self, parent, title, value):
        card = ctk.CTkFrame(
            parent, fg_color=PANEL, corner_radius=14, height=84,
            border_width=2, border_color=PANEL
        )
        card.pack(side="left", fill="both", expand=True, padx=4)
        card.pack_propagate(False)
        self.card_frames.append(card)

        ctk.CTkLabel(
            card, text=title, text_color=MUTED,
            font=(FONT, 10, "bold")
        ).pack(anchor="w", padx=16, pady=(14, 2))

        label = ctk.CTkLabel(
            card, text=value, text_color=ACCENT,
            font=(FONT, 22, "bold")
        )
        label.pack(anchor="w", padx=16)
        return label

    # --------------------------------------------------------
    # Animation loop (~60 fps, time-based so it stays smooth)
    # --------------------------------------------------------

    def tick(self):
        now = perf_counter()
        t = now - self.t0
        busy = self.worker_running

        dt = min(now - self.last_frame, 0.05)
        self.last_frame = now
        ease = 1 - math.exp(-dt * 6)  # не зависит от FPS

        # Mascot: bob (фаза копится — смена скорости без рывков)
        self.bob_speed += ((9.0 if busy else 2.2) - self.bob_speed) * ease
        self.bob_amp += ((3.0 if busy else 2.0) - self.bob_amp) * ease
        self.bob_phase += dt * self.bob_speed
        dy = math.sin(self.bob_phase) * self.bob_amp
        jt = now - self.jump_start
        if 0 <= jt < 0.6:
            dy -= 22 * math.sin(math.pi * jt / 0.6)
        self.mascot.move("m", 0, dy - self.last_dy)
        self.last_dy = dy

        self.look_speed += ((5.0 if busy else 1.3) - self.look_speed) * ease
        self.look_phase += dt * self.look_speed
        dx = math.sin(self.look_phase) * 2.5
        self.mascot.move("pupil", dx - self.last_dx, 0)
        self.last_dx = dx

        # Progress bar: левый и правый край плавно едут к цели
        w = self.bar.winfo_width()
        if w > 1:
            if self.bar_mode == "indet":
                blob = 0.28
                s = (t * 0.6) % 1.0
                s = s * s * (3 - 2 * s)  # плавный разгон и торможение
                pos = (1 + blob) * s - blob
                tl = min(1.0, max(0.0, pos))
                tr = min(1.0, max(0.0, pos + blob))
                if self._bar_locked:
                    self.bar_l, self.bar_r = tl, tr
                else:
                    # переход из полосы/пустоты в «бегущий блок» без скачка
                    k = 1 - math.exp(-dt * 9)
                    self.bar_l += (tl - self.bar_l) * k
                    self.bar_r += (tr - self.bar_r) * k
                    if (abs(tl - self.bar_l) < 0.01
                            and abs(tr - self.bar_r) < 0.01):
                        self._bar_locked = True
            else:
                self._bar_locked = False
                tgt = self.bar_target
                # правый край: плавно, но не медленнее минимальной скорости
                diff = tgt - self.bar_r
                step = diff * (1 - math.exp(-dt * 4.5))
                if diff > 0:
                    step = max(step, min(diff, dt * 0.05))
                self.bar_r += step
                if abs(tgt - self.bar_r) < 0.0008:
                    self.bar_r = tgt
                # левый край уезжает к нулю (после indet)
                self.bar_l += (0.0 - self.bar_l) * (1 - math.exp(-dt * 8))
                if self.bar_l < 0.0008:
                    self.bar_l = 0.0
            self.bar.coords(
                self.bar_fill,
                w * self.bar_l, 0, w * self.bar_r, 6
            )

        # Mascot blink
        if now >= self.next_blink:
            self.mascot.itemconfigure("eye", state="hidden")
            self.mascot.itemconfigure("pupil", state="hidden")
            self.blink_end = now + 0.13
            self.next_blink = now + random.uniform(2.0, 5.0)
        elif self.blink_end and now >= self.blink_end:
            self.mascot.itemconfigure("eye", state="normal")
            self.mascot.itemconfigure("pupil", state="normal")
            self.blink_end = 0.0

        # Progress bar colour pulse while busy
        if busy:
            k = (math.sin(t * 4) + 1) / 2
            a = (0xB8, 0xF5, 0x5B)
            b = (0x5B, 0xE8, 0xF5)
            col = "#%02x%02x%02x" % tuple(
                int(a[i] + (b[i] - a[i]) * k) for i in range(3)
            )
            self.bar.itemconfigure(self.bar_fill, fill=col)
        else:
            self.bar.itemconfigure(self.bar_fill, fill=ACCENT)

        # Count-up animation for the stat cards
        for i, lbl in enumerate(self.card_labels):
            tgt = self.card_tgt[i]
            cur = self.card_cur[i]
            cur += (tgt - cur) * (1 - math.exp(-dt * 9))
            if abs(tgt - cur) < 0.6:
                cur = tgt
            self.card_cur[i] = cur
            txt = format_size(int(cur)) if i == 3 else str(int(round(cur)))
            if txt != self.card_txt[i]:
                self.card_txt[i] = txt
                lbl.configure(text=txt)

        # Rotating quips while busy
        if busy and now >= self.next_quip:
            self.quip_label.configure(text=random.choice(BUSY_QUIPS))
            self.next_quip = now + 2.4

        try:
            self.fx_tick(now, dt, t, busy)
        except Exception:
            pass

        self.after(16, self.tick)

    def on_window_configure(self, event):
        if event.widget is self:
            self._resizing_until = perf_counter() + 0.15

    def _scaling(self):
        try:
            return float(self._get_window_scaling())
        except Exception:
            return 1.0

    def animate_size(self, w, h, duration=0.32):
        """Плавно меняет размер окна (ease-in-out), позиция не меняется."""
        sc = self._scaling()
        w0 = self.winfo_width() / sc
        h0 = self.winfo_height() / sc
        self._win_anim = token = object()
        t0 = perf_counter()

        def step():
            if self._win_anim is not token:
                return
            k = min(1.0, (perf_counter() - t0) / duration)
            e = k * k * (3 - 2 * k)
            self.geometry(
                f"{int(w0 + (w - w0) * e)}x{int(h0 + (h - h0) * e)}"
            )
            if k < 1.0:
                self.after(12, step)

        step()

    def toggle_zoom(self):
        """F11: плавно разворачивает окно на весь экран и обратно."""
        sc = self._scaling()
        if self._zoomed_small is None:
            self._zoomed_small = (
                self.winfo_width() / sc, self.winfo_height() / sc
            )
            self.geometry("+0+0")
            self.animate_size(
                self.winfo_screenwidth() / sc,
                (self.winfo_screenheight() - 80) / sc
            )
        else:
            w, h = self._zoomed_small
            self._zoomed_small = None
            self.animate_size(w, h)

    def set_face(self, state):
        if self.mouth is not None:
            self.mascot.delete(self.mouth)

        if state == "busy":
            self.mouth = self.mascot.create_oval(
                36, 54, 48, 64, fill=DARK, outline="", tags=("m",)
            )
        elif state == "happy":
            self.mouth = self.mascot.create_arc(
                28, 44, 56, 66, start=200, extent=140,
                style="arc", outline=DARK, width=3, tags=("m",)
            )
        elif state == "sad":
            self.mouth = self.mascot.create_arc(
                30, 54, 54, 70, start=20, extent=140,
                style="arc", outline=DARK, width=3, tags=("m",)
            )
        else:
            self.mouth = self.mascot.create_arc(
                30, 46, 54, 64, start=200, extent=140,
                style="arc", outline=DARK, width=3, tags=("m",)
            )
        self.mascot.move(self.mouth, 58, 8 + self.last_dy)

    def fade_in(self):
        try:
            a = float(self.attributes("-alpha"))
            if a < 1.0:
                self.attributes("-alpha", min(1.0, a + 0.08))
                self.after(25, self.fade_in)
        except Exception:
            pass

    def type_text(self, label, text, i=0, token=None):
        """Typewriter effect for a label."""
        if token is None:
            self._type_token += 1
            token = self._type_token
            label.configure(text_color=ACCENT)
        if token != self._type_token:
            return
        label.configure(text=text[:i])
        if i < len(text):
            self.after(28, lambda: self.type_text(label, text, i + 1, token))

    def on_mascot_click(self, event=None):
        self.jump_start = perf_counter()
        self.burst(n=14)
        self.type_text(self.speech, random.choice(MASCOT_JOKES))
        self.clear_speech(3500)

    def clear_speech(self, delay=3500):
        """Через delay мс плавно растворяет реплику маскота."""
        token = self._type_token
        self.after(delay, lambda: self.fade_speech(token, 0))

    def fade_speech(self, token, step):
        if token != self._type_token:
            return  # началась новая реплика
        if step >= 10:
            self.speech.configure(text="", text_color=ACCENT)
            return
        k = step / 10
        a = (0xB8, 0xF5, 0x5B)
        b = (0x15, 0x15, 0x1C)
        col = "#%02x%02x%02x" % tuple(
            int(a[i] + (b[i] - a[i]) * k) for i in range(3)
        )
        self.speech.configure(text_color=col)
        self.after(35, lambda: self.fade_speech(token, step + 1))

    def begin_busy(self, status, indeterminate=True):
        self.worker_running = True
        self.status_label.configure(text=status)
        self.bar_target = 0.0
        self._bar_locked = False
        self.bar_mode = "indet" if indeterminate else "det"
        self.next_quip = 0.0
        self.set_face("busy")
        self.set_controls_enabled(False)

    def end_busy(self, face="happy"):
        self.worker_running = False
        self.bar_mode = "det"
        self.bar_target = 1.0
        self.set_face(face)
        self.set_controls_enabled(True)
        # Радостный прыжок и фраза по завершении
        self.jump_start = perf_counter()
        if face == "happy":
            self.burst(n=20)
            self.type_text(self.speech, random.choice(DONE_QUIPS))
            self.clear_speech(3000)

    # --------------------------------------------------------
    # Mode switching
    # --------------------------------------------------------

    def change_mode(self, value):
        if self.worker_running:
            messagebox.showinfo(
                "y0m files",
                "Подожди, я ещё считаю. Не отвлекай 🙈"
            )
            self.mode_switch.set(self.mode)
            return

        self.mode = value
        self.title_label.configure(text=value)

        if value == "Tree Explorer":
            self.table_title.configure(
                text="Содержимое текущей папки"
            )
            self.calculate_button.configure(
                text="📊  Пересчитать размеры подпапок"
            )
            self.bottom_hint.configure(
                text="Размеры считаются для папок в этом каталоге"
            )
            if self.current_path:
                self.load_tree_directory()
            else:
                self.status_label.configure(
                    text="Выбери папку для начала"
                )
                self.clear_table()
                self.filter_items()
        else:
            self.table_title.configure(
                text="Самые большие объекты"
            )
            self.calculate_button.configure(
                text="📊  Полное сканирование"
            )
            self.bottom_hint.configure(
                text="Полный анализ всех вложенных объектов"
            )
            if self.current_path:
                self.start_full_scan(self.current_path)
            else:
                self.status_label.configure(
                    text="Выбери папку для полного сканирования"
                )
                self.clear_table()
                self.filter_items()

    # --------------------------------------------------------
    # Folder selection and navigation
    # --------------------------------------------------------

    def set_path(self, path):
        self.current_path = path
        self.path_label.configure(text="📁  " + path)

    def open_current(self, force=False):
        if self.mode == "Tree Explorer":
            self.load_tree_directory(force)
        else:
            self.start_full_scan(self.current_path)

    def choose_folder(self):
        if self.worker_running:
            return

        folder = filedialog.askdirectory(
            title="Выбери папку или диск"
        )
        if not folder:
            return

        self.history = []
        self.set_path(os.path.abspath(folder))
        self.open_current()

    def go_back(self):
        if self.worker_running or not self.history:
            return
        self.set_path(self.history.pop())
        self.open_current()

    def go_up(self):
        if self.worker_running or not self.current_path:
            return
        parent = os.path.dirname(self.current_path.rstrip("\\/"))
        if parent and parent != self.current_path:
            self.navigate_to(parent)

    def navigate_to(self, path):
        if self.worker_running or not os.path.isdir(path):
            return
        if self.current_path:
            self.history.append(self.current_path)
        self.set_path(os.path.abspath(path))
        self.open_current()

    def refresh(self):
        if self.worker_running or not self.current_path:
            return
        self.sidebar_quip.configure(text=random.choice(SIDEBAR_QUIPS))
        # Обновить = игнорировать кэш и посчитать заново
        self.tree_cache.pop(self.cache_key(self.current_path), None)
        self.open_current(force=True)

    # --------------------------------------------------------
    # Tree Explorer
    # --------------------------------------------------------

    def cache_key(self, path):
        return os.path.normcase(os.path.abspath(path))

    def show_cached(self, cached):
        """Instantly show previously calculated sizes."""
        self.scan_token += 1  # отменяем возможные старые события
        self.items = [dict(item) for item in cached]
        self.item_by_path = {item["path"]: item for item in self.items}

        folders = sum(1 for i in self.items if i["is_dir"])
        files = sum(1 for i in self.items if not i["is_dir"])
        archives = sum(1 for i in self.items if i["type"] == "АРХИВ")
        total = sum(i["size"] or 0 for i in self.items if not i["is_dir"])
        self.update_cards(folders, files, archives, total)

        self.bar_mode = "det"
        self.bar_l = 0.0
        self.bar_r = 0.0
        self.bar_target = 1.0
        self.filter_items()
        self.status_label.configure(
            text=f"Из кэша ⚡ объектов: {len(self.items)} · ↻ чтобы пересчитать"
        )
        self.quip_label.configure(text=size_quip(total))
        self.set_face("happy")
        self.jump_start = perf_counter()

    def load_tree_directory(self, force=False):
        """List only direct children; calculate each direct subfolder size."""
        if not force:
            cached = self.tree_cache.get(self.cache_key(self.current_path))
            if cached is not None:
                self.show_cached(cached)
                return

        self.scan_token += 1
        token = self.scan_token
        self.items = []
        self.item_by_path = {}
        self.clear_table()
        self.filter_items()

        self.begin_busy(
            "Читаю папку и считаю размеры подпапок...",
            indeterminate=True
        )

        threading.Thread(
            target=self.tree_worker,
            args=(self.current_path, token),
            daemon=True
        ).start()

        self.start_polling()

    def tree_worker(self, folder, token):
        def should_stop():
            return token != self.scan_token

        try:
            entries = []

            # Read only direct children of current directory.
            with os.scandir(folder) as iterator:
                for entry in iterator:
                    try:
                        if entry.is_symlink():
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            entries.append({
                                "name": entry.name,
                                "type": "ПАПКА",
                                "size": None,
                                "path": entry.path,
                                "is_dir": True
                            })
                        elif entry.is_file(follow_symlinks=False):
                            size = entry.stat(
                                follow_symlinks=False
                            ).st_size
                            is_archive = entry.name.lower().endswith(
                                ARCHIVES
                            )
                            entries.append({
                                "name": entry.name,
                                "type": "АРХИВ" if is_archive else "ФАЙЛ",
                                "size": size,
                                "path": entry.path,
                                "is_dir": False
                            })
                    except OSError:
                        continue

            folder_entries = [
                item for item in entries if item["is_dir"]
            ]

            # Files are known right away; folder sizes come later.
            self.events.put((
                "tree_started", token, entries, len(folder_entries)
            ))

            for index, item in enumerate(folder_entries, start=1):
                if should_stop():
                    return
                size = get_folder_size(item["path"], should_stop)
                if should_stop():
                    return

                self.events.put((
                    "folder_size", token, item["path"], size,
                    index, len(folder_entries)
                ))

            self.events.put(("tree_done", token))

        except Exception as error:
            self.events.put(("error", token, str(error)))

    # --------------------------------------------------------
    # Full Scan
    # --------------------------------------------------------

    def start_full_scan(self, folder):
        self.scan_token += 1
        token = self.scan_token
        self.full_results = []
        self.clear_table()
        self.filter_items()

        self.begin_busy(
            "Полное сканирование всех вложенных папок...",
            indeterminate=True
        )

        threading.Thread(
            target=self.full_scan_worker,
            args=(folder, token),
            daemon=True
        ).start()

        self.start_polling()

    def scan_dir(self, path, token, results, counters):
        """Recursive bottom-up scan. Returns total size of `path`."""
        total = 0
        try:
            with os.scandir(path) as iterator:
                for entry in iterator:
                    if token != self.scan_token:
                        return 0
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            total += self.scan_dir(
                                entry.path, token, results, counters
                            )
                        elif entry.is_file(follow_symlinks=False):
                            size = entry.stat(
                                follow_symlinks=False
                            ).st_size
                            total += size
                            counters["files"] += 1
                            counters["bytes"] += size

                            is_archive = entry.name.lower().endswith(
                                ARCHIVES
                            )
                            if is_archive:
                                counters["archives"] += 1
                            results.append((
                                size, entry.path,
                                "АРХИВ" if is_archive else "ФАЙЛ"
                            ))

                            if counters["files"] % 2500 == 0:
                                time.sleep(0.0005)
                                self.events.put((
                                    "scan_status", token,
                                    f"Папок: {counters['folders']} | "
                                    f"Файлов: {counters['files']}"
                                ))
                    except OSError:
                        continue
        except OSError:
            pass

        counters["folders"] += 1
        results.append((total, path, "ПАПКА"))
        return total

    def full_scan_worker(self, folder, token):
        try:
            results = []
            counters = {
                "files": 0, "folders": 0,
                "archives": 0, "bytes": 0
            }

            self.scan_dir(folder, token, results, counters)

            if token != self.scan_token:
                return

            results.sort(key=lambda item: item[0], reverse=True)

            self.events.put((
                "full_done", token, results,
                counters["files"], counters["folders"],
                counters["archives"], counters["bytes"]
            ))

        except Exception as error:
            self.events.put(("error", token, str(error)))

    # --------------------------------------------------------
    # Queue polling: all UI changes happen on main thread
    # --------------------------------------------------------

    def start_polling(self):
        if not self._polling:
            self._polling = True
            self.after(50, self.poll_events)

    def poll_events(self):
        try:
            for _ in range(200):
                event = self.events.get_nowait()
                kind = event[0]
                token = event[1]

                if token != self.scan_token:
                    continue

                if kind == "tree_started":
                    self.start_tree_view(event[2], event[3])

                elif kind == "folder_size":
                    self.update_folder_size(*event[2:])

                elif kind == "tree_done":
                    self.finish_tree()

                elif kind == "scan_status":
                    self.status_label.configure(text=event[2])

                elif kind == "full_done":
                    self.finish_full_scan(*event[2:])

                elif kind == "error":
                    self.finish_error(event[2])

        except queue.Empty:
            pass

        if self.worker_running:
            self.after(50, self.poll_events)
        else:
            self._polling = False

    # --------------------------------------------------------
    # Tree Explorer: live updates
    # --------------------------------------------------------

    def update_cards(self, folders, files, archives, total):
        # Значения плавно «накручиваются» в tick()
        self.card_tgt = [folders, files, archives, total]

    def start_tree_view(self, entries, total_folders):
        self.items = entries
        self.item_by_path = {item["path"]: item for item in entries}

        folders = sum(1 for item in entries if item["is_dir"])
        files = sum(1 for item in entries if not item["is_dir"])
        archives = sum(1 for item in entries if item["type"] == "АРХИВ")
        total = sum(
            item["size"] or 0 for item in entries if not item["is_dir"]
        )
        self.update_cards(folders, files, archives, total)

        self.bar_mode = "det"
        self.bar_target = 0.04 if total_folders else 1.0
        self.status_label.configure(
            text=(
                f"Найдено объектов: {len(entries)}. "
                f"Считаю размеры {total_folders} папок..."
            )
        )
        self.filter_items()

    def update_folder_size(self, path, size, index, total):
        item = self.item_by_path.get(path)
        if item is not None:
            item["size"] = size
            row = self.row_ids.get(path)
            if row is not None and self.tree.exists(row):
                self.tree.set(row, "size", size_text(size))
                self.tree.item(row, tags=size_tag(size))

        self.bar_target = 0.04 + 0.96 * (index / total)
        self.status_label.configure(
            text=f"Размеры папок: {index} из {total}"
        )

    def finish_tree(self):
        entries = self.items
        grand_total = sum(item["size"] or 0 for item in entries)

        entries.sort(key=lambda item: item["size"] or 0, reverse=True)

        # Сохраняем посчитанные значения в кэш
        self.tree_cache[self.cache_key(self.current_path)] = [
            dict(item) for item in entries
        ]

        self.end_busy("happy")
        self.filter_items()

        self.status_label.configure(
            text=f"Готово. В текущей папке объектов: {len(entries)}"
        )
        self.quip_label.configure(
            text=f"{size_quip(grand_total)}"
        )

    # --------------------------------------------------------
    # Finish Full Scan
    # --------------------------------------------------------

    def finish_full_scan(
        self, results, files, folders, archives, total
    ):
        self.full_results = results
        self.update_cards(folders, files, archives, total)

        self.end_busy("happy")
        self.filter_items()

        self.status_label.configure(
            text=f"Полное сканирование завершено. Объектов: {len(results)}"
        )
        self.quip_label.configure(text=size_quip(total))

    def finish_error(self, error):
        self.end_busy("sad")
        self.status_label.configure(text="Ошибка операции")
        self.quip_label.configure(text="Что-то пошло не так 😬")
        messagebox.showerror("y0m files - Ошибка", error)

    def set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.choose_button.configure(state=state)
        # The mode selector is disabled during a scan so the
        # active worker cannot be confused with another mode.
        self.mode_switch.configure(state=state)

    # --------------------------------------------------------
    # Table rendering and filtering
    # --------------------------------------------------------

    def clear_table(self):
        self.tree.delete(*self.tree.get_children())
        self.row_ids = {}
        self.row_data = {}
        self._hover_row = None

    def update_headings(self):
        for col, name in self.heading_names.items():
            arrow = ""
            if col == self.sort_col:
                arrow = "  ▼" if self.sort_rev else "  ▲"
            self.tree.heading(col, text=name + arrow)

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = col
            self.sort_rev = (col == "size")
        self.update_headings()
        self.filter_items()

    def sort_key(self, name, kind, size, path):
        col = self.sort_col
        if col == "name":
            return name.lower()
        if col == "type":
            return kind
        if col == "size":
            return size or 0
        return path.lower()

    def sorted_by_col(self, rows, key, size_of):
        """
        Сортировка по выбранной колонке; внутри равных значений
        (например, одного типа) всегда по размеру — от большего к меньшему.
        Python-сортировка устойчива, поэтому две стадии работают верно.
        """
        rows.sort(key=size_of, reverse=True)
        rows.sort(key=key, reverse=self.sort_rev)
        return rows

    def on_search_key(self, event=None):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(150, self.filter_items)

    def filter_items(self, event=None):
        self._search_job = None
        query = self.search.get().lower().strip()
        self.clear_table()

        shown = 0

        if self.mode == "Tree Explorer":
            visible = [
                item for item in self.items
                if not query or query in item["name"].lower()
            ]
            self.sorted_by_col(
                visible,
                key=lambda it: self.sort_key(
                    it["name"], it["type"], it["size"], it["path"]
                ),
                size_of=lambda it: it["size"] or 0
            )
            for item in visible:
                icon = ICONS.get(item["type"], "📄")
                row = self.tree.insert(
                    "",
                    "end",
                    values=(
                        f"{icon}  {item['name']}",
                        item["type"],
                        size_text(item["size"]),
                        item["path"]
                    ),
                    tags=size_tag(item["size"])
                )
                self.row_ids[item["path"]] = row
                self.row_data[row] = (item["type"], item["path"])
                shown += 1

        else:
            # Берём до 1000 самых больших совпадений, затем сортируем их
            matched = []
            for size, path, kind in self.full_results:
                name = os.path.basename(path) or path
                if (
                    query
                    and query not in name.lower()
                    and query not in path.lower()
                ):
                    continue
                matched.append((size, path, kind, name))
                if len(matched) >= 1000:
                    break

            self.sorted_by_col(
                matched,
                key=lambda m: self.sort_key(m[3], m[2], m[0], m[1]),
                size_of=lambda m: m[0] or 0
            )
            for size, path, kind, name in matched:
                icon = ICONS.get(kind, "📄")
                row = self.tree.insert(
                    "",
                    "end",
                    values=(
                        f"{icon}  {name}",
                        kind,
                        size_text(size),
                        path
                    ),
                    tags=size_tag(size)
                )
                self.row_data[row] = (kind, path)
                shown += 1

        self.update_empty_state(shown)

    def update_empty_state(self, shown):
        if shown > 0 or self.worker_running and self.items:
            self.empty_label.place_forget()
            return

        if not self.current_path:
            text = random.choice(EMPTY_QUIPS)
        elif self.worker_running:
            text = "Ищу, что тут у тебя лежит... 🔍"
        elif self.search.get().strip():
            text = "Ничего не нашлось 🦗\nПопробуй другое слово"
        else:
            text = "Папка пустая. Совсем-совсем 🕳️"

        self.empty_label.configure(text=text)
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    # --------------------------------------------------------
    # Double click / open in Explorer
    # --------------------------------------------------------

    def on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return

        self.tree.selection_set(row)
        kind, path = self.row_data.get(row, (None, None))
        if not path:
            return

        if self.mode == "Tree Explorer" and kind == "ПАПКА":
            self.navigate_to(path)
        else:
            self.open_selected()

    def open_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(
                "y0m files", "Сначала выбери файл или папку 👆"
            )
            return

        # Путь берём из своих данных, а не из Tcl-значений таблицы
        # (там пробелы, скобки и т.п. могут исказиться).
        kind, path = self.row_data.get(selected[0], (None, None))
        if not path:
            return
        path = os.path.abspath(os.path.normpath(path))

        if not os.path.exists(path):
            messagebox.showerror(
                "Ошибка", "Объект больше не существует. Улетел 🕊️"
            )
            return

        try:
            if sys.platform.startswith("win"):
                # Командой одной строкой с кавычками: при передаче списком
                # пробелы в пути ломают /select, и Проводник открывает
                # «Документы» вместо нужного файла.
                if os.path.isdir(path):
                    subprocess.Popen(f'explorer "{path}"')
                else:
                    subprocess.Popen(f'explorer /select,"{path}"')
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                target = path if os.path.isdir(path) else os.path.dirname(path)
                subprocess.Popen(["xdg-open", target])
        except OSError as error:
            messagebox.showerror("Ошибка Проводника", str(error))

    # --------------------------------------------------------
    # Recalculate direct child folder sizes in Tree Explorer
    # --------------------------------------------------------

    def calculate_selected_folder(self):
        if self.worker_running:
            return

        if self.mode == "Full Scan":
            if self.current_path:
                self.start_full_scan(self.current_path)
            return

        self.refresh()

    # --------------------------------------------------------
    # Эффекты: конфетти, уведомления, подсветка карточек и строк
    # --------------------------------------------------------

    def fx_tick(self, now, dt, t, busy):
        # Конфетти вокруг маскота
        if self.particles:
            alive = []
            for item, x, y, vx, vy, age, life, r in self.particles:
                age += dt
                if age >= life:
                    self.mascot.delete(item)
                    continue
                vx *= 1 - dt * 1.2
                vy += 420 * dt
                x += vx * dt
                y += vy * dt
                rr = r * (1 - age / life) + 0.3
                self.mascot.coords(item, x - rr, y - rr, x + rr, y + rr)
                alive.append([item, x, y, vx, vy, age, life, r])
            self.particles = alive

        # Карточки светятся, когда над ними курсор
        px, py = self.winfo_pointerxy()
        for i, card in enumerate(self.card_frames):
            x0, y0 = card.winfo_rootx(), card.winfo_rooty()
            inside = (
                x0 <= px < x0 + card.winfo_width()
                and y0 <= py < y0 + card.winfo_height()
            )
            goal = 1.0 if inside else 0.0
            h = self.card_hover[i]
            nh = h + (goal - h) * (1 - math.exp(-dt * 12))
            if abs(goal - nh) < 0.01:
                nh = goal
            if nh != h:
                self.card_hover[i] = nh
                card.configure(border_color=lerp_color(PANEL, ACCENT, nh))

        # Кнопка «Выбрать папку» пульсирует, пока папка не выбрана
        if not self.current_path and not busy:
            col = lerp_color(ACCENT, "#E4FF9E", (math.sin(t * 3) + 1) / 2)
            if col != self._pulse_col:
                self._pulse_col = col
                self.choose_button.configure(fg_color=col)
            self._pulsing = True
        elif self._pulsing:
            self._pulsing = False
            self._pulse_col = None
            self.choose_button.configure(fg_color=ACCENT)

        # Уведомление выезжает справа, висит и уезжает обратно
        if self.toast_t0:
            el = now - self.toast_t0
            hold = self.toast_hold
            if el < 0.35:
                off = (1 - el / 0.35) ** 3
            elif el < 0.35 + hold:
                off = 0.0
            elif el < 0.7 + hold:
                off = ((el - 0.35 - hold) / 0.35) ** 3
            else:
                off = None
                self.toast.place_forget()
                self.toast_t0 = 0.0
            if off is not None:
                self.toast.place(
                    relx=1.0, rely=1.0, anchor="se",
                    x=-24 + 460 * off, y=-24
                )

    def burst(self, colors=None, n=22):
        """Фонтан конфетти из маскота."""
        colors = colors or [ACCENT, CYAN, WARN, PINK, TEXT]
        for _ in range(n):
            a = random.uniform(0, math.tau)
            speed = random.uniform(70, 210)
            item = self.mascot.create_oval(
                0, 0, 1, 1, fill=random.choice(colors), outline=""
            )
            self.particles.append([
                item, 100.0, 52.0,
                math.cos(a) * speed, math.sin(a) * speed - 90,
                0.0, random.uniform(0.7, 1.3), random.uniform(2.0, 4.2)
            ])

    def show_toast(self, text, kind="ok"):
        color = {"ok": ACCENT, "warn": WARN, "bad": BAD}.get(kind, ACCENT)
        self.toast.configure(border_color=color)
        self.toast_label.configure(text=text)
        self.toast_hold = 2.0 + len(text) * 0.03
        self.toast_t0 = perf_counter()

    def row_tags(self, row):
        tags = self.tree.item(row)["tags"]
        if isinstance(tags, str):
            tags = [tags] if tags else []
        return list(tags)

    def set_hover(self, row):
        old = self._hover_row
        if old == row:
            return
        if old and self.tree.exists(old):
            self.tree.item(
                old, tags=[t for t in self.row_tags(old) if t != "hover"]
            )
        if row and self.tree.exists(row):
            self.tree.item(row, tags=self.row_tags(row) + ["hover"])
        self._hover_row = row

    def on_tree_motion(self, event):
        self.set_hover(self.tree.identify_row(event.y) or None)

    def run_bg(self, func, callback):
        """Выполняет func в потоке, callback(result, error) — в главном."""
        box = {}

        def work():
            try:
                box["ok"] = func()
            except Exception as error:
                box["err"] = error
            box["done"] = True

        threading.Thread(target=work, daemon=True).start()

        def check():
            if box.get("done"):
                callback(box.get("ok"), box.get("err"))
            else:
                self.after(80, check)

        self.after(80, check)

    def face_if_idle(self, face):
        if not self.worker_running:
            self.set_face(face)

    # --------------------------------------------------------
    # Удаление в корзину
    # --------------------------------------------------------

    def delete_selected(self):
        if self.worker_running or self.deleting:
            self.show_toast("Подожди, я ещё занят ⏳", "warn")
            return

        targets = []  # (строка, путь из таблицы, абсолютный путь)
        for row in self.tree.selection():
            kind, raw = self.row_data.get(row, (None, None))
            if raw:
                targets.append(
                    (row, raw, os.path.abspath(os.path.normpath(raw)))
                )

        if not targets:
            self.show_toast("Сначала выбери, что удалять 👆", "warn")
            self.jump_start = perf_counter()
            return

        names = [os.path.basename(p) or p for _, _, p in targets]
        shown = "\n".join("•  " + n for n in names[:6])
        if len(names) > 6:
            shown += f"\n…и ещё {len(names) - 6}"
        note = (
            "\nСлишком большое для корзины удалится насовсем."
            if IS_WIN else ""
        )
        if not messagebox.askyesno(
            "y0m files - Удаление",
            f"Отправить в корзину ({len(targets)}):\n\n{shown}\n{note}\n"
            "Продолжить?",
            icon="warning"
        ):
            return

        # Размеры запоминаем заранее — понадобятся для пересчёта
        sizes = {}
        if self.mode == "Full Scan":
            by_path = {p: sz for sz, p, _ in self.full_results}
            for _, raw, _ in targets:
                sizes[raw] = by_path.get(raw) or 0
        else:
            for _, raw, _ in targets:
                item = self.item_by_path.get(raw)
                sizes[raw] = (item["size"] or 0) if item else 0

        self.deleting = True
        origin = (self.current_path, self.mode)
        self.face_if_idle("busy")
        self.status_label.configure(text=f"Удаляю объектов: {len(targets)}...")
        self.quip_label.configure(text="Прощайте, байтики 🫡")

        def work():
            ok, fail = [], []
            for _, raw, path in targets:
                try:
                    if os.path.lexists(path):
                        move_to_trash(path)
                    ok.append(raw)
                except Exception as error:
                    fail.append((raw, str(error)))
            return ok, fail

        self.run_bg(
            work,
            lambda res, err: self.after_delete(
                res, err, targets, sizes, origin
            )
        )

    def after_delete(self, result, error, targets, sizes, origin):
        if error is not None or not result:
            result = ([], [(raw, str(error)) for _, raw, _ in targets])
        ok, fail = result
        ok_set = set(ok)

        same_view = origin == (self.current_path, self.mode)
        rows = []
        if same_view:
            rows = [
                row for row, raw, _ in targets
                if raw in ok_set and self.tree.exists(row)
            ]

        if rows:
            self.tree.selection_set(())
            for row in rows:
                self.tree.item(row, tags=("dying",))
            self.fade_rows(
                0, lambda: self.finish_delete(ok, fail, sizes, same_view)
            )
        else:
            self.finish_delete(ok, fail, sizes, same_view)

    def fade_rows(self, step, done):
        """Удаляемые строки краснеют и растворяются."""
        if step > 9:
            done()
            return
        k = step / 9
        self.tree.tag_configure(
            "dying",
            background=lerp_color("#4A1F24", PANEL, k),
            foreground=lerp_color(BAD, PANEL, k)
        )
        self.after(28, lambda: self.fade_rows(step + 1, done))

    def finish_delete(self, ok, fail, sizes, same_view):
        self.deleting = False
        self.tree_cache.clear()  # размеры родительских папок изменились
        nc = os.path.normcase

        gone_keys = {nc(os.path.abspath(p)) for p in ok}
        gone_prefix = tuple(k + os.sep for k in gone_keys)

        def gone(path):
            k = nc(path)
            return k in gone_keys or k.startswith(gone_prefix)

        # Считаем освобождённое место; вложенные объекты не дублируем
        freed = 0
        adj = {}
        for raw in ok:
            size = sizes.get(raw, 0)
            key = nc(os.path.abspath(raw))
            others = tuple(g + os.sep for g in gone_keys if g != key)
            if not size or key.startswith(others):
                continue
            freed += size
            parent = os.path.dirname(os.path.abspath(raw))
            while True:
                pk = nc(parent)
                adj[pk] = adj.get(pk, 0) + size
                up = os.path.dirname(parent)
                if up == parent:
                    break
                parent = up

        if ok and same_view:
            self.items = [i for i in self.items if not gone(i["path"])]
            self.item_by_path = {i["path"]: i for i in self.items}

            if self.full_results:
                new = []
                for size, path, kind in self.full_results:
                    if gone(path):
                        continue
                    if kind == "ПАПКА" and adj:
                        size = max(0, size - adj.get(nc(path), 0))
                    new.append((size, path, kind))
                new.sort(key=lambda r: r[0], reverse=True)
                self.full_results = new

            if self.mode == "Full Scan":
                files = [r for r in self.full_results if r[2] != "ПАПКА"]
                self.update_cards(
                    len(self.full_results) - len(files),
                    len(files),
                    sum(1 for r in files if r[2] == "АРХИВ"),
                    sum(r[0] for r in files)
                )
            else:
                self.update_cards(
                    sum(1 for i in self.items if i["is_dir"]),
                    sum(1 for i in self.items if not i["is_dir"]),
                    sum(1 for i in self.items if i["type"] == "АРХИВ"),
                    sum(i["size"] or 0 for i in self.items
                        if not i["is_dir"])
                )
            self.filter_items()

        if ok:
            msg = f"Удалено: {len(ok)}"
            msg += f" · освободил {format_size(freed)} 🎉" if freed else " 🎉"
            self.show_toast(msg, "ok")
            self.status_label.configure(text=msg)
            self.quip_label.configure(text="Лёгкость в диске необыкновенная")
            self.burst()
            self.jump_start = perf_counter()
            self.face_if_idle("happy")
        else:
            self.face_if_idle("sad")
            self.show_toast("Ничего не удалилось 😬", "bad")

        if fail:
            lines = "\n".join(
                f"•  {os.path.basename(p) or p}: {e}" for p, e in fail[:5]
            )
            messagebox.showerror(
                "y0m files - Не всё удалилось",
                f"Не удалось удалить ({len(fail)}):\n\n{lines}"
            )

        self.refresh_trash_info()

    # --------------------------------------------------------
    # Корзина
    # --------------------------------------------------------

    def refresh_trash_info(self):
        def done(info, error):
            self.trash_info = info if error is None else None
            if self.trash_info is None:
                text = "Корзина: недоступна"
            elif self.trash_info[1] == 0:
                text = "Корзина: пусто ✨"
            else:
                text = (
                    f"Корзина: {format_size(self.trash_info[0])}"
                    f" · {self.trash_info[1]} шт."
                )
            self.trash_label.configure(text=text)

        self.run_bg(recycle_info, done)

    def empty_trash(self):
        if self.trash_busy:
            return

        info = self.trash_info
        if info is not None and info[1] == 0:
            self.show_toast("Корзина и так пустая 🕳️", "warn")
            return

        detail = ""
        if info:
            detail = (
                f"\n\nВнутри: {info[1]} шт. · {format_size(info[0])}."
            )
        if not messagebox.askyesno(
            "y0m files - Корзина",
            "Очистить корзину насовсем?" + detail
            + "\nВосстановить файлы будет нельзя.",
            icon="warning"
        ):
            return

        self.trash_busy = True
        freed = info[0] if info else 0
        self.trash_label.configure(text="Корзина: чищу... 🧹")
        self.face_if_idle("busy")
        self.run_bg(
            empty_recycle,
            lambda res, err: self.after_empty(err, freed)
        )

    def after_empty(self, error, freed):
        self.trash_busy = False
        if error is not None:
            self.face_if_idle("sad")
            self.show_toast("Корзина не поддалась 😬", "bad")
            messagebox.showerror("y0m files - Корзина", str(error))
        else:
            msg = "Корзина чиста ✨"
            if freed:
                msg += f" · освободил {format_size(freed)}"
            self.show_toast(msg, "ok")
            self.burst([ACCENT, CYAN, PINK, WARN, "#FFFFFF"], n=30)
            self.jump_start = perf_counter()
            self.face_if_idle("happy")
            self.type_text(self.speech, "Фух, вынес мусор! 🗑️")
            self.clear_speech(3000)
        self.refresh_trash_info()

    def on_close(self):
        self.scan_token += 1
        self.destroy()


if __name__ == "__main__":
    app = Nexus()
    app.mainloop()
