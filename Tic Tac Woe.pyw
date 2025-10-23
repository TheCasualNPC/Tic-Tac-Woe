# tic_tac_toe_cheater_deluxe.pyw
# Tic Tac Woe — fullscreen, right-side HUD (big status), bottom-right buttons,
# in-canvas settings (with credits), hover/click feedback, quality presets,
# border chaos on stretch/fullscreen, falling confetti on exploit wins, blink-free
# drawing, instant status updates, Enter/Space reset, and no top banner.

import os, sys, math, random, warnings
import tkinter as tk
from tkinter import ttk, messagebox

# Silence pygame banner and setuptools warnings
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*")

# ---------------- Configuration ----------------
MUSIC_ENABLED = True
MUSIC_CANDIDATES = ["game_theme.ogg", "game_theme.mp3", "game_theme.wav"]
DEFAULT_VOLUME = 0.35

CHEAT_WINDOW_MS = 250
BASE_BOARD_PX = 360
LINE_W = 4
CHAOS_FPS = 3
CHAOS_SIZE_TRIGGER = 500

HUMAN, AI, EMPTY = "O", "X", " "
WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)

class Game:
    THEMES = {
        "Neon Night":   {"bg":"#111318","grid":"#2a2e39","o":"#66d9ef","x":"#f92672","win":"#ffd866","pixel":"#ffd866","hover_stipple":"gray50","hud_fg":"#e6edf3"},
        "Terminal":     {"bg":"#000000","grid":"#00aa00","o":"#00ff7f","x":"#00ffff","win":"#ffff00","pixel":"#00ff00","hover_stipple":"gray75","hud_fg":"#c8ffc8"},
        "Blueberry":    {"bg":"#0d1b2a","grid":"#1b263b","o":"#e0fbfc","x":"#98c1d9","win":"#ee6c4d","pixel":"#ee6c4d","hover_stipple":"gray50","hud_fg":"#e0fbfc"},
        "Monochrome":   {"bg":"#1b1b1b","grid":"#444444","o":"#cfcfcf","x":"#e6e6e6","win":"#f5f5f5","pixel":"#f5f5f5","hover_stipple":"gray50","hud_fg":"#f0f0f0"},
        "Absurd Candy": {"bg":"#241023","grid":"#fe5f55","o":"#7ae582","x":"#e4ff1a","win":"#fee440","pixel":"#fe5f55","hover_stipple":"gray50","hud_fg":"#ffe6ff"},
    }
    AI_TAUNTS = ["I win. Obviously.","I win, idiot.","I win, you lose.","I win, get good.","I win, try harder."]
    HUMAN_WIN_LINES = ["You win. You cheated. Shameful.","You win. Exploit < honor. Noted.","You win. Lag wizard.","You win. I’ll allow it."]

    def __init__(self, root):
        self.root = root
        root.title("Tic Tac Woe")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.theme_name = "Neon Night"
        self.theme = self.THEMES[self.theme_name]
        self.status = tk.StringVar(value="You are a Zero. You go first.")
        self._status_emphasis = False

        self.board = [EMPTY]*9
        self.game_over = False
        self.pending_human_end = None
        self.human_moves_this_turn = 0

        self.music_loaded = False
        self._pygame = None
        self.muted = False
        self.volume = DEFAULT_VOLUME

        self.quality = 2  # 0 Low, 1 Medium, 2 High (Ultra maps to High)

        self._resize_job = None
        self._chaos_job = None
        self._confetti_job = None
        self.fullscreen = False

        # Root shell + canvas
        self.shell = tk.Frame(root, bg=self.theme["bg"])
        self.shell.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1); root.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.shell, bg=self.theme["bg"], highlightthickness=0, cursor="arrow")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.shell.rowconfigure(0, weight=1); self.shell.columnconfigure(0, weight=1)

        # Settings overlay
        self.overlay_mask = tk.Frame(self.canvas, bg="#000000")
        self.settings_panel = self._build_settings_panel(self.canvas)
        self._credits_label = None  # set in _build_settings_panel

        # Geometry state
        self.logical_board_px = BASE_BOARD_PX
        self.ox = self.oy = 0

        # HUD layout cache and button rects
        self.hud = {}  # keys: x0,y0,w,h,status_rect,buttons:[(name,(x0,y0,x1,y1))]
        self.hud_hover = None

        # Hover/pulse/confetti
        self.hover_cell = None
        self._confetti = []
        self._confetti_g = 0.38

        # Redraw triggers
        self.status.trace_add("write", lambda *_: self._redraw_status_only())

        # Bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda e: self.clear_hover())
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen(not self.fullscreen))
        self.root.bind("<Escape>", self._esc_handler)
        self.root.bind("<Return>", lambda e: self.reset())
        self.root.bind("<KP_Enter>", lambda e: self.reset())
        self.root.bind("<space>", lambda e: self.reset())

        # First draw + fullscreen
        self.update_layout_metrics()
        self.draw_board(force_base=True)
        self.toggle_fullscreen(True)

        if MUSIC_ENABLED:
            self.init_music()

    # ---------------- Settings overlay with credits ----------------
    def _build_settings_panel(self, parent):
        panel = tk.Frame(parent, bg="#1a1d24", bd=0, highlightthickness=0)

        title = tk.Label(panel, text="Settings", font=("DejaVu Sans", 14, "bold"),
                         fg="#e6edf3", bg="#1a1d24")
        title.grid(row=0, column=0, columnspan=2, pady=(10,6), padx=16, sticky="w")

        tk.Label(panel, text="Color Theme", fg="#c9d1d9", bg="#1a1d24"
                ).grid(row=1, column=0, sticky="w", padx=16, pady=6)
        self.theme_cb = ttk.Combobox(panel, values=list(self.THEMES.keys()),
                                     state="readonly", width=20)
        self.theme_cb.set(self.theme_name)
        self.theme_cb.grid(row=1, column=1, sticky="e", padx=16, pady=6)

        tk.Label(panel, text="Music Volume", fg="#c9d1d9", bg="#1a1d24"
                ).grid(row=2, column=0, sticky="w", padx=16, pady=6)
        self.vol_var = tk.DoubleVar(value=self.volume)
        vol_scale = tk.Scale(panel, from_=0.0, to=1.0, resolution=0.01, orient="horizontal",
                             variable=self.vol_var, length=220, bg="#1a1d24", fg="#c9d1d9",
                             highlightthickness=0, troughcolor="#2a2e39",
                             command=lambda _=None: self._apply_volume(self.vol_var.get()))
        vol_scale.grid(row=2, column=1, sticky="e", padx=16, pady=6)

        self.mute_var = tk.BooleanVar(value=self.muted)
        ttk.Checkbutton(panel, text="Mute", variable=self.mute_var,
                        command=lambda: self._toggle_mute(self.mute_var.get())
                        ).grid(row=3, column=1, sticky="e", padx=16, pady=0)

        tk.Label(panel, text="Graphics Quality", fg="#c9d1d9", bg="#1a1d24"
                ).grid(row=4, column=0, sticky="w", padx=16, pady=6)
        self.q_cb = ttk.Combobox(panel, values=["Low","Medium","High","Ultra"],
                                 state="readonly", width=20)
        self.q_cb.set({0:"Low",1:"Medium",2:"High"}.get(self.quality, "High"))
        self.q_cb.grid(row=4, column=1, sticky="e", padx=16, pady=6)

        ttk.Button(panel, text="Toggle Fullscreen (F11)",
                   command=lambda: self.toggle_fullscreen(not self.fullscreen)
                   ).grid(row=5, column=1, sticky="e", padx=16, pady=6)

        btns = tk.Frame(panel, bg="#1a1d24")
        btns.grid(row=6, column=0, columnspan=2, pady=(12,6))
        ttk.Button(btns, text="Apply", command=self.apply_settings
                  ).grid(row=0, column=0, padx=8)
        ttk.Button(btns, text="Close", command=self.hide_settings_overlay
                  ).grid(row=0, column=1, padx=8)

        tk.Frame(panel, bg="#2a2e39", height=1
                ).grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(8,4))

        about = (
            "If you lose, The Clanker just did better >^_^>. Just outsmart it.\n"
            "Created by: Casual_NPC\n"
            "Music by: Casual_NPC"
        )
        self._credits_label = tk.Label(panel, text=about, justify="center",
                                       fg="#aeb6c2", bg="#1a1d24",
                                       font=("DejaVu Sans", 10))
        self._credits_label.configure(wraplength=480)
        self._credits_label.grid(row=8, column=0, columnspan=2, sticky="ew", padx=16, pady=(4,10))

        panel.grid_rowconfigure(8, weight=0)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)
        return panel

    def toggle_settings_overlay(self):
        if getattr(self, "_settings_visible", False):
            self.hide_settings_overlay()
        else:
            self.show_settings_overlay()

    def show_settings_overlay(self):
        if getattr(self, "_settings_visible", False): return
        self._settings_visible = True
        self._place_overlay_mask(); self._place_panel_center()
        self.overlay_mask.lift(); self.settings_panel.lift()
        self.theme_cb.set(self.theme_name)
        self.q_cb.set({0:"Low",1:"Medium",2:"High"}.get(self.quality, "High"))
        self.vol_var.set(self.volume); self.mute_var.set(self.muted)

    def hide_settings_overlay(self):
        if not getattr(self, "_settings_visible", False): return
        self._settings_visible = False
        try: self.overlay_mask.place_forget()
        except Exception: pass
        try: self.settings_panel.place_forget()
        except Exception: pass
        self.canvas.focus_set()

    def _place_overlay_mask(self):
        self.canvas.update_idletasks()
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.overlay_mask.configure(bg=self._dim(self.theme["bg"], 0.55))
        self.overlay_mask.place(x=0, y=0, width=w, height=h)

    def _place_panel_center(self):
        self.canvas.update_idletasks()
        target_w, target_h = 520, 400
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        pad = 40
        w = min(target_w, max(360, cw - pad))
        h = min(target_h, max(320, ch - pad))
        x = (cw - w)//2; y = (ch - h)//2
        self.settings_panel.place(x=x, y=y, width=w, height=h)
        if self._credits_label is not None:
            self._credits_label.configure(wraplength=max(240, w - 32))

    def apply_settings(self):
        chosen = self.theme_cb.get()
        force_base = False
        if chosen in self.THEMES and chosen != self.theme_name:
            self.theme_name = chosen
            self.theme = self.THEMES[chosen]
            force_base = True

        q = self.q_cb.get()
        if q == "Ultra":
            messagebox.showinfo("Ultra", "What do you expect from me?")
            self.quality = 2
        elif q == "High": self.quality = 2
        elif q == "Medium": self.quality = 1
        else: self.quality = 0

        self.hide_settings_overlay()
        self.manage_chaos_loop(force=True)
        self.draw_board(force_base=force_base)

    # ---------------- Helpers ----------------
    def _dim(self, hex_color, amt):
        hc = hex_color.lstrip("#")
        r = int(hc[0:2],16); g=int(hc[2:4],16); b=int(hc[4:6],16)
        r = int(r*(1-amt)); g=int(g*(1-amt)); b=int(b*(1-amt))
        return f"#{r:02x}{g:02x}{b:02x}"

    def set_status(self, text: str, emphasis: bool=False):
        self._status_emphasis = bool(emphasis)
        self.status.set(text)

    # ---------------- Geometry / resize ----------------
    def on_resize(self, _event):
        if getattr(self, "_settings_visible", False):
            self._place_overlay_mask(); self._place_panel_center()
        if self._resize_job is not None:
            try: self.root.after_cancel(self._resize_job)
            except Exception: pass
        self._resize_job = self.root.after(30, self._resized)

    def _resized(self):
        self._resize_job = None
        self.update_layout_metrics()
        self.draw_board()   # base rebuild only if needed
        self.manage_chaos_loop()

    def update_layout_metrics(self):
        self.canvas.update_idletasks()
        cw = max(3, self.canvas.winfo_width()); ch = max(3, self.canvas.winfo_height())
        board_size = max(120, min(cw, ch) - 2)
        self.logical_board_px = board_size
        self.ox = (cw - board_size)//2
        self.oy = (ch - board_size)//2

    def toggle_fullscreen(self, on: bool):
        self.fullscreen = bool(on)
        try:
            self.root.attributes("-fullscreen", self.fullscreen)
        except Exception:
            self.root.state("zoomed" if self.fullscreen else "normal")
        self.manage_chaos_loop(force=True)
        self.draw_board(force_base=True)

    def _esc_handler(self, _e):
        if getattr(self, "_settings_visible", False): self.hide_settings_overlay()
        elif self.fullscreen: self.toggle_fullscreen(False)

    # ---------------- Music ----------------
    def init_music(self):
        old_stderr = sys.stderr
        try:
            sys.stderr = open(os.devnull, "w")
            try:
                import pygame
            finally:
                sys.stderr.close(); sys.stderr = old_stderr
        except Exception:
            self.music_loaded = False; return

        try:
            pygame = sys.modules["pygame"]
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.init()
            self._pygame = pygame
            song_path = None
            for name in MUSIC_CANDIDATES:
                p = resource_path(name)
                if os.path.exists(p):
                    song_path = p; break
            if song_path:
                pygame.mixer.music.load(song_path)
                pygame.mixer.music.set_volume(0.0 if self.muted else self.volume)
                pygame.mixer.music.play(-1)
                self.music_loaded = True
            else:
                self.music_loaded = False
        except Exception:
            self.music_loaded = False

    def _apply_volume(self, v):
        self.volume = float(v)
        if self.music_loaded and not self.muted:
            try: self._pygame.mixer.music.set_volume(self.volume)
            except Exception: pass

    def _toggle_mute(self, muted):
        self.muted = bool(muted)
        if self.music_loaded:
            try: self._pygame.mixer.music.set_volume(0.0 if self.muted else self.volume)
            except Exception: pass

    # ---------------- Game logic ----------------
    def winner(self, b):
        for a,c,d in WIN_LINES:
            if b[a]!=EMPTY and b[a]==b[c]==b[d]: return b[a]
        return None

    def moves(self, b): return [i for i,c in enumerate(b) if c==EMPTY]
    def terminal(self, b): return self.winner(b) is not None or not self.moves(b)

    def score(self, b, depth):
        w = self.winner(b)
        if w==AI: return 10 - depth
        if w==HUMAN: return depth - 10
        return 0

    def minimax(self, b, depth, maximizing, alpha=-math.inf, beta=math.inf):
        if self.terminal(b): return self.score(b, depth), None
        best_move = None
        if maximizing:
            best_val = -math.inf
            for m in self.moves(b):
                b[m]=AI
                val,_=self.minimax(b, depth+1, False, alpha, beta)
                b[m]=EMPTY
                if val>best_val: best_val, best_move = val, m
                alpha = max(alpha, val)
                if beta<=alpha: break
            return best_val, best_move
        else:
            best_val = math.inf
            for m in self.moves(b):
                b[m]=HUMAN
                val,_=self.minimax(b, depth+1, True, alpha, beta)
                b[m]=EMPTY
                if val<best_val: best_val, best_move = val, m
                beta = min(beta, val)
                if beta<=alpha: break
            return best_val, best_move

    def ai_move(self):
        if self.game_over: return
        _, m = self.minimax(self.board, 0, True)
        if m is not None: self.board[m] = AI
        self.draw_board()
        self.check_end_or_continue(ai_just_moved=True)

    def force_win(self):
        candidate = sorted(WIN_LINES, key=lambda line: -sum(1 for i in line if self.board[i]==AI))
        for a,c,d in candidate:
            self.board[a]=self.board[c]=self.board[d]=AI
            if self.winner(self.board)==AI: return
        for i in (0,4,8): self.board[i]=AI

    # ---------------- Interaction ----------------
    def on_click(self, event):
        if getattr(self, "_settings_visible", False): return
        if self._hud_hit(event.x, event.y): return
        if self.game_over: return

        cs = max(1, self.logical_board_px//3)
        bx0 = self.ox; by0 = self.oy
        bx1 = bx0 + 3*cs; by1 = by0 + 3*cs
        if not (bx0 <= event.x <= bx1 and by0 <= event.y <= by1): return

        col = max(0, min(2, int((event.x - bx0)//cs)))
        row = max(0, min(2, int((event.y - by0)//cs)))
        idx = row*3 + col
        if self.board[idx] != EMPTY: return

        self.board[idx] = HUMAN
        self.human_moves_this_turn = min(self.human_moves_this_turn+1, 2)
        if self.quality >= 2: self.click_pulse(row, col)
        self.draw_board()

        if self.winner(self.board)==HUMAN:
            self.human_exploit_victory(); return

        if self.pending_human_end is not None:
            try: self.root.after_cancel(self.pending_human_end)
            except Exception: pass
        self.pending_human_end = self.root.after(CHEAT_WINDOW_MS, self.end_human_phase)

    def on_motion(self, event):
        if self._hud_hover(event.x, event.y): return
        if self.quality < 2 or getattr(self, "_settings_visible", False):
            self.clear_hover(); return

        cs = max(1, self.logical_board_px//3)
        bx0 = self.ox; by0 = self.oy
        bx1 = bx0 + 3*cs; by1 = by0 + 3*cs
        if not (bx0 <= event.x <= bx1 and by0 <= event.y <= by1):
            self.clear_hover(); return

        col = max(0, min(2, int((event.x - bx0)//cs)))
        row = max(0, min(2, int((event.y - by0)//cs)))
        idx = row*3 + col
        if self.board[idx]==EMPTY and self.hover_cell!=(row,col):
            self.hover_cell=(row,col); self.draw_hover()
        elif self.board[idx]!=EMPTY:
            self.clear_hover()

    def clear_hover(self):
        self.hover_cell=None; self.canvas.delete("hover")

    def draw_hover(self):
        self.canvas.delete("hover")
        if not self.hover_cell: return
        r,c = self.hover_cell
        cs = max(1, self.logical_board_px//3)
        x0 = self.ox + c*cs + 2; y0 = self.oy + r*cs + 2
        x1 = x0 + cs - 4;       y1 = y0 + cs - 4
        self.canvas.create_rectangle(x0,y0,x1,y1, fill=self.theme["o"], outline="",
                                     stipple=self.theme.get("hover_stipple","gray50"), tags=("hover",))

    def click_pulse(self, row, col):
        cs = max(1, self.logical_board_px//3)
        x0 = self.ox + col*cs + 3; y0 = self.oy + row*cs + 3
        x1 = x0 + cs - 6;         y1 = y0 + cs - 6
        tag = "clickpulse"
        self.canvas.delete(tag)
        rect = self.canvas.create_rectangle(x0,y0,x1,y1, fill=self.theme["win"], outline="", tags=(tag,))
        steps = ["gray25","gray50","gray75"]
        def step(i=0):
            if i>=len(steps): self.canvas.delete(tag); return
            try: self.canvas.itemconfigure(rect, stipple=steps[i])
            except Exception: pass
            self.root.after(50, lambda: step(i+1))
        step(0)

    def end_human_phase(self):
        self.pending_human_end = None
        if self.check_end_or_continue(ai_just_moved=False):
            self.human_moves_this_turn = 0; return
        self.root.after(150, self.ai_turn_end)

    def ai_turn_end(self):
        self.ai_move(); self.human_moves_this_turn = 0

    def human_exploit_victory(self):
        self.set_status(random.choice(self.HUMAN_WIN_LINES), emphasis=False)
        self.game_over = True
        self.draw_board()
        if self.quality >= 1:
            self.start_confetti_fall()

    def check_end_or_continue(self, ai_just_moved):
        w = self.winner(self.board)
        if w == AI:
            self.set_status(random.choice(self.AI_TAUNTS), emphasis=True)
            self.game_over=True; return True
        if w == HUMAN:
            self.set_status(random.choice(self.HUMAN_WIN_LINES), emphasis=False)
            self.game_over=True
            if self.quality >= 1: self.start_confetti_fall()
            return True
        if not self.moves(self.board):
            self.set_status("A draw? Reality disagrees.", emphasis=True)
            self.force_win(); self.draw_board()
            self.set_status(random.choice(self.AI_TAUNTS), emphasis=True)
            self.game_over=True; return True
        self.set_status("Your turn. You're slower than a Windows update on hotel Wi-Fi -_____-" if ai_just_moved else "I think faster than you...", emphasis=False)
        return False

    # ---------------- Drawing ----------------
    def draw_board(self, force_base=False):
        c = self.canvas
        c.update_idletasks()
        cw, ch = max(3, c.winfo_width()), max(3, c.winfo_height())

        # Wider HUD so status text breathes; buttons at bottom-right
        hud_w = max(300, int(cw * 0.28))
        board_max_w = cw - hud_w - 16
        size = max(120, min(self.logical_board_px, board_max_w, ch - 16))
        cs = max(1, size//3)
        self.ox = 8 + (board_max_w - size)//2
        self.oy = (ch - size)//2

        base_sig = (cw, ch, size, self.theme_name, hud_w)
        if force_base or getattr(self, "_base_sig", None) != base_sig:
            self._base_sig = base_sig
            for tag in ("base","hud","hud_status","hud_status_bg"):
                c.delete(tag)

            # Background and board grid
            c.create_rectangle(0,0,cw,ch, fill=self.theme["bg"], outline="", tags=("base",))
            if cs >= 2:
                for i in range(1,3):
                    x = self.ox + i*cs; y = self.oy + i*cs
                    c.create_line(x, self.oy, x, self.oy+3*cs, width=LINE_W, fill=self.theme["grid"], tags=("base",))
                    c.create_line(self.ox, y, self.ox+3*cs, y, width=LINE_W, fill=self.theme["grid"], tags=("base",))

            # HUD panel
            hud_x0 = cw - hud_w
            c.create_rectangle(hud_x0, 0, cw, ch, fill=self._dim(self.theme["bg"], 0.12),
                               outline=self.theme["grid"], width=2, tags=("hud",))

            # Layout HUD areas
            pad = 24
            btn_h = int(max(44, ch * 0.07))
            btn_gap = int(max(12, ch * 0.02))
            btn_total = 3*btn_h + 2*btn_gap
            btn_top = ch - pad - btn_total
            status_x = hud_x0 + 16
            status_y = 16
            status_w = hud_w - 32
            status_h = max(80, btn_top - status_y - pad)  # expand until just above buttons

            # Save metrics
            self.hud = {
                "x0": hud_x0, "y0": 0, "w": hud_w, "h": ch,
                "status": (status_x, status_y, status_w, status_h),
                "buttons_top": btn_top, "btn_h": btn_h, "btn_gap": btn_gap
            }

            # Draw status block background
            self._draw_status_bg()
            # Draw buttons bottom-right
            self._draw_buttons()

            # Initial status text
            self._draw_status_text()

        # Marks-only refresh
        c.delete("marks"); c.delete("hover"); c.delete("clickpulse")
        if cs >= 2:
            r = cs//3; lw = max(4, cs//14)
            for i, mark in enumerate(self.board):
                cx = self.ox + (i%3)*cs + cs//2
                cy = self.oy + (i//3)*cs + cs//2
                if mark=='O':
                    c.create_oval(cx-r,cy-r,cx+r,cy+r, width=lw, outline=self.theme["o"], tags=("marks",))
                elif mark=='X':
                    c.create_line(cx-r,cy-r,cx+r,cy+r, width=lw, fill=self.theme["x"], tags=("marks",))
                    c.create_line(cx+r,cy-r,cx-r,cy+r, width=lw, fill=self.theme["x"], tags=("marks",))
            w = self.winner(self.board)
            if w:
                for a,c3,d in WIN_LINES:
                    if self.board[a]==self.board[c3]==self.board[d]!=EMPTY:
                        ax = self.ox + (a%3)*cs + cs//2; ay = self.oy + (a//3)*cs + cs//2
                        dx = self.ox + (d%3)*cs + cs//2; dy = self.oy + (d//3)*cs + cs//2
                        c.create_line(ax,ay,dx,dy, width=max(6, cs//10), fill=self.theme["win"], tags=("marks",))
                        break

        if self.quality >= 2 and self.hover_cell: self.draw_hover()
        self.manage_chaos_loop()

    # ----- HUD pieces -----
    def _draw_status_bg(self):
        c = self.canvas
        c.delete("hud_status_bg")
        x, y, w, h = self.hud["status"]
        fill = self.theme["win"] if self._status_emphasis else self._dim(self.theme["bg"], 0.20)
        c.create_rectangle(x, y, x+w, y+h, fill=fill, outline=self.theme["grid"], width=2, tags=("hud_status_bg","hud"))

    def _draw_status_text(self):
        c = self.canvas
        c.delete("hud_status")
        x, y, w, h = self.hud["status"]
        fg = "#111111" if self._status_emphasis else self.theme["hud_fg"]
        # keep text size sensible: big but not meme-huge
        font_size = max(16, min(42, int(h * 0.22)))
        c.create_text(x+10, y+10, anchor="nw",
                      text=self.status.get(), fill=fg,
                      font=("DejaVu Sans", font_size, "bold"),
                      width=w-20, tags=("hud_status","hud"))

    def _draw_buttons(self):
        c = self.canvas
        # remove old buttons
        c.delete("hud_buttons")
        x0 = self.hud["x0"]; ch = self.hud["h"]; hud_w = self.hud["w"]
        pad = 18
        btn_h = self.hud["btn_h"]
        btn_gap = self.hud["btn_gap"]
        btn_top = self.hud["buttons_top"]

        labels = [("NEW GAME","new"), ("SETTINGS","settings"), ("EXIT","exit")]
        self.hud["buttons"] = []
        for i, (label,name) in enumerate(labels):
            y0 = btn_top + i*(btn_h + btn_gap)
            y1 = y0 + btn_h
            bx0 = x0 + pad; bx1 = x0 + hud_w - pad
            fill = self._dim(self.theme["o"], 0.72) if self.hud_hover == name else self._dim(self.theme["o"], 0.82)
            c.create_rectangle(bx0,y0,bx1,y1, fill=fill, outline=self.theme["grid"], width=2, tags=("hud_buttons","hud"))
            c.create_text((bx0+bx1)//2, (y0+y1)//2, text=label,
                          fill=self._dim("#000000", 0.1),
                          font=("DejaVu Sans", max(16, int(btn_h*0.45)), "bold"),
                          tags=("hud_buttons","hud"))
            self.hud["buttons"].append((name,(bx0,y0,bx1,y1)))

    def _redraw_status_only(self):
        # Recolor bg if emphasis flipped; redraw status text only otherwise
        self._draw_status_bg()
        self._draw_status_text()

    def _hud_hover(self, x, y):
        prev = self.hud_hover
        self.hud_hover = None
        for name, (x0,y0,x1,y1) in self.hud.get("buttons", []):
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.hud_hover = name; break
        if prev != self.hud_hover:
            self.canvas.config(cursor="hand2" if self.hud_hover else "arrow")
            self._draw_buttons()
        # Also treat moving over status as non-hover
        return self.hud_hover is not None

    def _hud_hit(self, x, y):
        if self._hud_hover(x, y):
            if self.hud_hover == "new": self.reset()
            elif self.hud_hover == "settings": self.toggle_settings_overlay()
            elif self.hud_hover == "exit": self.on_close()
            return True
        return False

    # ---------------- Chaos (border mini-boards) ----------------
    def chaos_should_run(self):
        if self.quality == 0: return False
        if self.fullscreen and self.quality >= 1: return True
        if self.quality >= 2 and self.logical_board_px >= CHAOS_SIZE_TRIGGER: return True
        return False

    def manage_chaos_loop(self, force=False):
        want = self.chaos_should_run()
        running = self._chaos_job is not None
        if force or want != running:
            if want: self.start_chaos()
            else: self.stop_chaos()

    def start_chaos(self):
        if self._chaos_job: return
        self.chaos_tick()

    def stop_chaos(self):
        if self._chaos_job:
            try: self.root.after_cancel(self._chaos_job)
            except Exception: pass
            self._chaos_job = None
        self.canvas.delete("chaos")

    def chaos_tick(self):
        self.canvas.delete("chaos")
        self.draw_border_chaos()
        self._chaos_job = self.root.after(int(1000/CHAOS_FPS), self.chaos_tick)

    def draw_border_chaos(self):
        c = self.canvas
        cw, ch = c.winfo_width(), c.winfo_height()
        hud_w = self.hud.get("w", max(300, int(cw * 0.28)))
        board_max_w = cw - hud_w - 16
        board = min(board_max_w, ch - 16, self.logical_board_px)
        pad=8
        left   = (0,0, self.ox-pad, ch)
        right  = (self.ox+board+pad,0, cw - hud_w, ch)
        top    = (self.ox-pad,0, self.ox+board+pad, self.oy-pad)
        bottom = (self.ox-pad, self.oy+board+pad, self.ox+board+pad, ch)

        for x0,y0,x1,y1 in (left,right,top,bottom):
            area_w, area_h = max(0,x1-x0), max(0,y1-y0)
            area = area_w*area_h
            if area <= 0: continue
            count = min(40, max(2, area//18000))
            for _ in range(count): self._draw_mini_win(c, x0,y0,x1,y1)

    def _draw_mini_win(self, c, x0,y0,x1,y1):
        if x1-x0 < 20 or y1-y0 < 20: return
        size = random.randint(18,36)
        max_x, max_y = max(x0, x1-size), max(y0, y1-size)
        px, py = random.randint(x0, max_x), random.randint(y0, max_y)
        c.create_rectangle(px,py,px+size,py+size, fill="", outline=self.theme["grid"], tags=("chaos",))
        cell = max(1, size//3); lw = max(1, size//16)
        line = random.choice(WIN_LINES)
        for i in range(1,3):
            c.create_line(px+i*cell,py, px+i*cell,py+size, fill=self.theme["grid"], width=1, tags=("chaos",))
            c.create_line(px,py+i*cell, px+size,py+i*cell, fill=self.theme["grid"], width=1, tags=("chaos",))
        for idx in range(9):
            r, q = idx//3, idx%3
            cx = px + q*cell + cell//2; cy = py + r*cell + cell//2
            if idx in line:
                rr = cell//3
                c.create_line(cx-rr,cy-rr,cx+rr,cy+rr, fill=self.theme["pixel"], width=lw, tags=("chaos",))
                c.create_line(cx+rr,cy-rr,cx-rr,cy+rr, fill=self.theme["pixel"], width=lw, tags=("chaos",))
            else:
                if random.random()<0.2:
                    rr = cell//3
                    c.create_oval(cx-rr,cy-rr,cx+rr,cy+rr, outline=self.theme["grid"], width=1, tags=("chaos",))

    # ---------------- Confetti: falling animation ----------------
    def start_confetti_fall(self):
        self.canvas.delete("confetti")
        self._confetti = []
        c = self.canvas
        cw, ch = c.winfo_width(), c.winfo_height()
        count = max(60, min(160, cw // 8))
        for _ in range(count):
            x = random.uniform(self.ox, self.ox + self.logical_board_px)
            y = self.oy - random.uniform(10, 120)
            vx = random.uniform(-0.8, 0.8)
            vy = random.uniform(0.5, 3.0)
            r = random.randint(2, 5)
            fill = self._rand_color()
            self._confetti.append({"x":x,"y":y,"vx":vx,"vy":vy,"r":r,"fill":fill})
        self.confetti_tick()

    def confetti_tick(self):
        if not self._confetti:
            self.canvas.delete("confetti"); self._confetti_job = None; return
        c = self.canvas
        cw, ch = c.winfo_width(), c.winfo_height()
        c.delete("confetti")
        alive = []
        g = self._confetti_g
        air = 0.995
        for p in self._confetti:
            p["vy"] += g
            p["vx"] *= air
            p["vy"] *= air
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            x, y, r = p["x"], p["y"], p["r"]
            if y - r > ch + 20:
                continue
            c.create_oval(x-r, y-r, x+r, y+r, fill=p["fill"], outline="", tags=("confetti",))
            alive.append(p)
        self._confetti = alive
        self._confetti_job = self.root.after(33, self.confetti_tick)

    def _rand_color(self):
        return "#{:02x}{:02x}{:02x}".format(
            random.randint(120,255),random.randint(120,255),random.randint(120,255)
        )

    # ---------------- Reset / Exit ----------------
    def reset(self):
        if self.pending_human_end is not None:
            try: self.root.after_cancel(self.pending_human_end)
            except Exception: pass
            self.pending_human_end = None
        if self._confetti_job:
            try: self.root.after_cancel(self._confetti_job)
            except Exception: pass
            self._confetti_job = None
        self.canvas.delete("confetti")
        self.board = [EMPTY]*9; self.game_over=False; self.human_moves_this_turn=0
        self.set_status("You are a Zero. Click a square. You go first.", emphasis=False)
        self.draw_board()
        self.canvas.update_idletasks()

    def on_close(self):
        try:
            if self.music_loaded and self._pygame:
                self._pygame.mixer.music.stop()
                self._pygame.quit()
        except Exception: pass
        self.root.destroy()

# ---------------- Main ----------------
if __name__ == "__main__":
    root = tk.Tk()
    Game(root)
    root.mainloop()
