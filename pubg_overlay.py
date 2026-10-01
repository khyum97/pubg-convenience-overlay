"""
PUBG Convenience HUD Overlay
A lightweight, 100% safe (zero-ban, zero-memory-hook) game companion for PUBG.
Features:
- Loot & Attachment Checklist (Hold TAB to view)
- Grenade Cooking Timer (F3) with audio cues
- Bluezone Phase Countdown (F2)
- Center Dot Crosshair (F1)
- Preset & Attachment toggles (F4, F5, F6, F7)
"""

import sys
import os
import json
import time
import threading
import winsound
import ctypes
from ctypes import wintypes
import tkinter as tk

from pubg_core import GameStateManager, BLUEZONE_PHASES

VK_MAP = {
    "VK_TAB": 0x09,
    "VK_CAPITAL": 0x14,
    "VK_F1": 0x70,
    "VK_F2": 0x71,
    "VK_F3": 0x72,
    "VK_F4": 0x73,
    "VK_F5": 0x74,
    "VK_F6": 0x75,
    "VK_F7": 0x76,
    "VK_F8": 0x77,
    "VK_F9": 0x78,
    "VK_F10": 0x79,
    "VK_F11": 0x7A,
    "VK_F12": 0x7B,
    "VK_OEM_3": 0xC0,      # `~` key
    "VK_M": 0x4D,          # M key (In-game Map)
    "VK_ESCAPE": 0x1B,     # ESC key
    "VK_LMENU": 0xA4,      # Left Alt
    "VK_XBUTTON1": 0x05,   # Mouse 4
    "VK_XBUTTON2": 0x06,   # Mouse 5
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class PubgOverlayApp:
    TRANS_COLOR = "#000001"

    def __init__(self):
        self.state = GameStateManager()
        self.load_config()

        self.root = tk.Tk()
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.setup_window()
        self.setup_canvas()
        self.apply_click_through()

        # UI visibility flags
        self.loot_visible = False
        self.map_hud_visible = False
        self.map_pins_visible = False
        self.running = True

        # OCR state & Toast notifications
        self.ocr_enabled = self.config["settings"].get("ocr_enabled", False)
        self.last_ocr_time = 0.0
        self.toast_msg = ""
        self.toast_expire = 0.0

        # Index tracker for toggling items via hotkey
        self.w1_item_idx = 0
        self.w2_item_idx = 0

        # Start background hotkey and timer thread
        self.worker_thread = threading.Thread(target=self.hotkey_and_timer_loop, daemon=True)
        self.worker_thread.start()

        # Start Tkinter refresh loop (60 FPS approx 16ms)
        self.root.after(20, self.update_ui)

    def load_config(self):
        self.config = {
            "hotkeys": {
                "loot_hud_hold": "VK_TAB",
                "crosshair_toggle": "VK_F1",
                "bluezone_advance": "VK_F2",
                "grenade_timer": "VK_F3",
                "preset_switch": "VK_F4",
                "toggle_part_w1": "VK_F5",
                "toggle_part_w2": "VK_F6",
                "reset_session": "VK_F7",
                "ocr_toggle": "VK_F8",
                "map_hud_toggle": "VK_OEM_3",
                "map_pins_toggle": "VK_M",
                "map_switch": "VK_F10",
                "exit_app": "VK_F9"
            },
            "settings": {
                "loot_hud_hold_mode": True,
                "ocr_enabled": False,
                "map_overlay_enabled": True,
                "sound_enabled": True,
                "crosshair_style": "dot",
                "crosshair_color": "#00FF66",
                "crosshair_size": 4
            }
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    self.config["hotkeys"].update(user_cfg.get("hotkeys", {}))
                    self.config["settings"].update(user_cfg.get("settings", {}))
            except Exception as e:
                print(f"[Warning] Failed to read config.json, using defaults: {e}")

    def setup_window(self):
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", self.TRANS_COLOR)
        self.root.config(bg=self.TRANS_COLOR)

    def setup_canvas(self):
        self.canvas = tk.Canvas(
            self.root,
            width=self.screen_width,
            height=self.screen_height,
            bg=self.TRANS_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

    def apply_click_through(self):
        """Configure Windows extended style to enable click-through transparent overlay"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        except Exception as e:
            print(f"[Warning] Could not set WS_EX_TRANSPARENT: {e}")

    def play_sound(self, freq: int, duration_ms: int):
        if self.config["settings"].get("sound_enabled", True):
            threading.Thread(target=lambda: winsound.Beep(freq, duration_ms), daemon=True).start()

    def show_toast(self, msg: str, duration: float = 2.0):
        self.toast_msg = msg
        self.toast_expire = time.time() + duration

    def trigger_ocr_scan(self):
        """Asynchronously capture screen and recognize inventory items via OCR"""
        now = time.time()
        if now - self.last_ocr_time < 2.0:
            return
        self.last_ocr_time = now

        def _worker():
            try:
                import asyncio
                import winocr
                from PIL import ImageGrab

                w, h = self.screen_width, self.screen_height
                # Focus on the inventory area (center to right screen)
                bbox = (int(w * 0.25), int(h * 0.1), int(w * 0.95), int(h * 0.9))
                shot = ImageGrab.grab(bbox=bbox)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(winocr.recognize_pil(shot, lang='ko'))
                loop.close()

                if res and res.text:
                    changes = self.state.update_from_ocr_text(res.text)
                    items = []
                    if changes["attachments"]:
                        items.extend(changes["attachments"])
                    if changes["consumables"]:
                        items.extend(changes["consumables"])
                    if items:
                        self.play_sound(1400, 60)
                        summary = ", ".join(items[:2])
                        self.show_toast(f"📷 [OCR 자동 파밍 감지] {summary}")
            except ImportError:
                self.show_toast("📷 [OCR] winocr 패키지가 필요합니다")
            except Exception as e:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def get_vk(self, name: str) -> int:
        return VK_MAP.get(name, 0)

    def is_key_down(self, vk: int) -> bool:
        if vk == 0:
            return False
        return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0

    def hotkey_and_timer_loop(self):
        """Thread monitoring hotkeys and advancing game state timers"""
        prev_states = {}
        last_timer_tick = time.time()

        while self.running:
            now = time.time()
            dt = now - last_timer_tick
            last_timer_tick = now

            # Tick timers in core
            if self.state.bluezone_active:
                self.state.tick_bluezone(dt)

            if self.state.grenade_active:
                event = self.state.tick_grenade(dt)
                if event == "danger":
                    self.play_sound(1200, 150)
                elif event == "throw_now":
                    self.play_sound(1600, 200)
                elif event == "detonated":
                    self.play_sound(500, 300)

            # Hotkey check
            hk = self.config["hotkeys"]

            # 1. Loot HUD (Hold or Toggle)
            loot_vk = self.get_vk(hk.get("loot_hud_hold", "VK_TAB"))
            loot_down = self.is_key_down(loot_vk)
            if self.config["settings"].get("loot_hud_hold_mode", True):
                self.loot_visible = loot_down
            else:
                if loot_down and not prev_states.get("loot", False):
                    self.loot_visible = not self.loot_visible

            # If TAB is pressed (inventory open) and OCR is enabled, scan screen
            if loot_down and self.ocr_enabled:
                self.trigger_ocr_scan()

            prev_states["loot"] = loot_down

            # 2. Crosshair Toggle (F1)
            f1_vk = self.get_vk(hk.get("crosshair_toggle", "VK_F1"))
            f1_down = self.is_key_down(f1_vk)
            if f1_down and not prev_states.get("f1", False):
                self.state.crosshair_enabled = not self.state.crosshair_enabled
                self.play_sound(900 if self.state.crosshair_enabled else 600, 60)
            prev_states["f1"] = f1_down

            # 3. Bluezone Advance (F2)
            f2_vk = self.get_vk(hk.get("bluezone_advance", "VK_F2"))
            f2_down = self.is_key_down(f2_vk)
            if f2_down and not prev_states.get("f2", False):
                self.state.start_or_advance_bluezone()
                self.play_sound(1000, 80)
            prev_states["f2"] = f2_down

            # 4. Grenade Cook (F3)
            f3_vk = self.get_vk(hk.get("grenade_timer", "VK_F3"))
            f3_down = self.is_key_down(f3_vk)
            if f3_down and not prev_states.get("f3", False):
                self.state.trigger_grenade_cook()
                if self.state.grenade_active:
                    self.play_sound(800, 100)
            prev_states["f3"] = f3_down

            # 5. Weapon Preset Switch (F4)
            f4_vk = self.get_vk(hk.get("preset_switch", "VK_F4"))
            f4_down = self.is_key_down(f4_vk)
            if f4_down and not prev_states.get("f4", False):
                self.state.next_preset()
                self.play_sound(1100, 70)
            prev_states["f4"] = f4_down

            # 6. Toggle W1 Attachment (F5)
            f5_vk = self.get_vk(hk.get("toggle_part_w1", "VK_F5"))
            f5_down = self.is_key_down(f5_vk)
            if f5_down and not prev_states.get("f5", False):
                w1 = self.state.current_preset["weapon1"]
                self.state.toggle_weapon1_attachment(self.w1_item_idx)
                self.w1_item_idx = (self.w1_item_idx + 1) % len(w1.attachments)
                self.play_sound(950, 50)
            prev_states["f5"] = f5_down

            # 7. Toggle W2 Attachment (F6)
            f6_vk = self.get_vk(hk.get("toggle_part_w2", "VK_F6"))
            f6_down = self.is_key_down(f6_vk)
            if f6_down and not prev_states.get("f6", False):
                w2 = self.state.current_preset["weapon2"]
                self.state.toggle_weapon2_attachment(self.w2_item_idx)
                self.w2_item_idx = (self.w2_item_idx + 1) % len(w2.attachments)
                self.play_sound(950, 50)
            prev_states["f6"] = f6_down

            # 8. Reset Session (F7)
            f7_vk = self.get_vk(hk.get("reset_session", "VK_F7"))
            f7_down = self.is_key_down(f7_vk)
            if f7_down and not prev_states.get("f7", False):
                self.state.reset_loot_session()
                self.state.reset_bluezone()
                self.play_sound(500, 150)
            prev_states["f7"] = f7_down

            # 8-2. OCR Toggle (F8)
            f8_vk = self.get_vk(hk.get("ocr_toggle", "VK_F8"))
            f8_down = self.is_key_down(f8_vk)
            if f8_down and not prev_states.get("f8", False):
                self.ocr_enabled = not self.ocr_enabled
                if self.ocr_enabled:
                    self.play_sound(1200, 60)
                    self.show_toast("📷 [OCR 자동 인식] ON: TAB 화면 자동 스캔")
                else:
                    self.play_sound(500, 80)
                    self.show_toast("📷 [OCR 자동 인식] OFF: 수동 모드")
            prev_states["f8"] = f8_down

            # 8-3. Map Info HUD Toggle (~ / tilde or configured key)
            map_vk = self.get_vk(hk.get("map_hud_toggle", "VK_OEM_3"))
            map_down = self.is_key_down(map_vk)
            if map_down and not prev_states.get("map_hud", False):
                self.map_hud_visible = not self.map_hud_visible
                status_txt = "표시" if self.map_hud_visible else "숨김"
                self.play_sound(1100 if self.map_hud_visible else 600, 60)
                self.show_toast(f"🗺️ [차량 & 비밀방 지도] {status_txt}")
            prev_states["map_hud"] = map_down

            # 8-4. Map Switch (F10)
            f10_vk = self.get_vk(hk.get("map_switch", "VK_F10"))
            f10_down = self.is_key_down(f10_vk)
            if f10_down and not prev_states.get("f10", False):
                new_map = self.state.next_map()
                self.play_sound(1050, 70)
                self.show_toast(f"🗺️ 현재 맵 변경: {new_map}")
            prev_states["f10"] = f10_down

            # 8-5. In-Game Map Direct Pin Overlay (M key or configured key)
            pins_vk = self.get_vk(hk.get("map_pins_toggle", "VK_M"))
            pins_down = self.is_key_down(pins_vk)
            if pins_down and not prev_states.get("pins", False):
                self.map_pins_visible = not self.map_pins_visible
                status_txt = "ON (지도 핀 표시)" if self.map_pins_visible else "OFF (지도 핀 숨김)"
                self.play_sound(1200 if self.map_pins_visible else 600, 50)
                self.show_toast(f"🗺️ [지도 핀 마커] {status_txt}")
            prev_states["pins"] = pins_down

            # ESC closes map pins overlay if open
            if self.map_pins_visible and self.is_key_down(0x1B):
                self.map_pins_visible = False

            # 9. Exit (F9)
            f9_vk = self.get_vk(hk.get("exit_app", "VK_F9"))
            f9_down = self.is_key_down(f9_vk)
            if f9_down and not prev_states.get("f9", False):
                self.running = False
                self.root.after(0, self.root.destroy)
                break
            prev_states["f9"] = f9_down

            time.sleep(0.02)

    def draw_crosshair(self):
        if not self.state.crosshair_enabled:
            return
        cx = self.screen_width // 2
        cy = self.screen_height // 2
        col = self.config["settings"].get("crosshair_color", "#00FF66")
        size = self.config["settings"].get("crosshair_size", 4)
        style = self.config["settings"].get("crosshair_style", "dot")

        if style == "dot":
            # Center dot with black border for high contrast
            self.canvas.create_oval(cx - size - 1, cy - size - 1, cx + size + 1, cy + size + 1, fill="#000000", outline="")
            self.canvas.create_oval(cx - size, cy - size, cx + size, cy + size, fill=col, outline="")
        elif style == "cross":
            gap = 4
            length = 9
            # Black shadow lines
            self.canvas.create_line(cx - gap - length, cy, cx - gap, cy, fill="#000000", width=3)
            self.canvas.create_line(cx + gap, cy, cx + gap + length, cy, fill="#000000", width=3)
            self.canvas.create_line(cx, cy - gap - length, cx, cy - gap, fill="#000000", width=3)
            self.canvas.create_line(cx, cy + gap, cx, cy + gap + length, fill="#000000", width=3)
            # Inner color lines
            self.canvas.create_line(cx - gap - length, cy, cx - gap, cy, fill=col, width=1.5)
            self.canvas.create_line(cx + gap, cy, cx + gap + length, cy, fill=col, width=1.5)
            self.canvas.create_line(cx, cy - gap - length, cx, cy - gap, fill=col, width=1.5)
            self.canvas.create_line(cx, cy + gap, cx, cy + gap + length, fill=col, width=1.5)

    def draw_grenade_hud(self):
        if not self.state.grenade_active:
            return
        cx = self.screen_width // 2
        cy = self.screen_height // 2 + 130
        rem = self.state.grenade_remaining_sec

        w, h = 260, 68
        x1, y1 = cx - w // 2, cy - h // 2
        x2, y2 = cx + w // 2, cy + h // 2

        # 1. Drop shadow
        self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 + 4, y2 + 4, fill="#020617", outline="")

        # 2. Main card & pulsating hazard border
        is_critical = rem <= 1.5
        border_col = "#EF4444" if is_critical else ("#F59E0B" if rem <= 2.5 else "#10B981")
        card_fill = "#180608" if is_critical else "#090E17"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=card_fill, outline=border_col, width=2)

        # 3. Top title tag
        header_text = "⚡ THROW NOW! (즉시 투척)" if is_critical else "💣 GRENADE FUSE COOKING"
        header_col = "#FCA5A5" if is_critical else "#94A3B8"
        self.canvas.create_text(cx, y1 + 16, text=header_text, fill=header_col, font=("Segoe UI", 9, "bold"))

        # 4. Large Digital Timer
        timer_col = "#FF2222" if is_critical else ("#FBBF24" if rem <= 2.5 else "#34D399")
        self.canvas.create_text(cx, cy + 2, text=f"{rem:.1f}s", fill=timer_col, font=("Segoe UI", 16, "bold"))

        # 5. Segmented Progress Bar
        bar_x1 = x1 + 16
        bar_x2 = x2 - 16
        bar_y1 = y2 - 14
        bar_y2 = y2 - 8
        bar_w = bar_x2 - bar_x1

        # Background track
        self.canvas.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, fill="#1E293B", outline="")

        # Filled track
        ratio = max(0.0, min(1.0, rem / 5.0))
        filled_w = int(bar_w * ratio)
        if filled_w > 0:
            self.canvas.create_rectangle(bar_x1, bar_y1, bar_x1 + filled_w, bar_y2, fill=border_col, outline="")

    def draw_bluezone_hud(self):
        if not self.state.bluezone_active:
            return
        cx = self.screen_width // 2
        top_y = 35
        phase_info = BLUEZONE_PHASES[self.state.current_phase_idx]
        rem = int(self.state.bluezone_remaining_sec)
        mm, ss = divmod(rem, 60)
        time_str = f"{mm:02d}:{ss:02d}"

        is_shrinking = self.state.bluezone_is_shrinking
        mode_str = "SHRINKING (축소 중)" if is_shrinking else "WAITING (대기 중)"
        theme_col = "#F43F5E" if is_shrinking else "#06B6D4"
        card_fill = "#160A10" if is_shrinking else "#081018"

        w, h = 340, 52
        x1, y1 = cx - w // 2, top_y
        x2, y2 = cx + w // 2, top_y + h

        # Drop shadow
        self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 + 4, y2 + 4, fill="#020617", outline="")
        # Outer Card
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=card_fill, outline=theme_col, width=2)

        # Phase indicator dots
        dot_str = " ".join(["●" if i <= self.state.current_phase_idx else "○" for i in range(8)])
        self.canvas.create_text(cx, top_y + 14, text=f"PHASE {phase_info['phase']}  [{dot_str}]", fill="#94A3B8", font=("Segoe UI", 8, "bold"))

        # Time & Mode
        self.canvas.create_text(cx - 50, top_y + 34, text=mode_str, fill=theme_col, font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(cx + 80, top_y + 34, text=time_str, fill="#FFFFFF", font=("Segoe UI", 13, "bold"))

    def draw_loot_hud(self):
        """High-end esports / commercial tactical inventory checklist HUD"""
        if not self.loot_visible:
            return

        panel_w = 360
        panel_h = 515
        px = self.screen_width - panel_w - 35
        py = 85

        # 1. Drop shadow
        self.canvas.create_rectangle(px + 6, py + 6, px + panel_w + 6, py + panel_h + 6, fill="#020617", outline="")

        # 2. Main Glass Card
        self.canvas.create_rectangle(px, py, px + panel_w, py + panel_h, fill="#090E17", outline="#1E293B", width=2)

        # 3. Header Titlebar
        self.canvas.create_rectangle(px, py, px + panel_w, py + 42, fill="#0F172A", outline="")
        self.canvas.create_line(px, py + 42, px + panel_w, py + 42, fill="#2563EB", width=1.5)

        # Title + Beacon
        self.canvas.create_oval(px + 14, py + 18, px + 22, py + 26, fill="#10B981", outline="")
        self.canvas.create_text(px + 28, py + 21, text="TACTICAL COMPANION PRO", anchor="w", fill="#38BDF8", font=("Segoe UI", 10, "bold"))

        # OCR Pill
        ocr_bg = "#064E3B" if self.ocr_enabled else "#1E293B"
        ocr_border = "#10B981" if self.ocr_enabled else "#475569"
        ocr_txt = "● OCR ON" if self.ocr_enabled else "○ OCR OFF"
        ocr_col = "#34D399" if self.ocr_enabled else "#94A3B8"
        self.canvas.create_rectangle(px + panel_w - 120, py + 11, px + panel_w - 55, py + 31, fill=ocr_bg, outline=ocr_border, width=1)
        self.canvas.create_text(px + panel_w - 87, py + 21, text=ocr_txt, fill=ocr_col, font=("Segoe UI", 8, "bold"))

        # Preset key badge
        self.canvas.create_text(px + panel_w - 14, py + 21, text="[F4]", anchor="e", fill="#64748B", font=("Segoe UI", 9, "bold"))

        curr_y = py + 54

        # Preset summary banner
        preset = self.state.current_preset
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + 26, fill="#0D1526", outline="#1E3A8A", width=1)
        self.canvas.create_text(px + 20, curr_y + 13, text=f"LOADOUT: {preset['name']}", anchor="w", fill="#93C5FD", font=("Segoe UI", 8, "bold"))
        curr_y += 34

        # Weapon 1 Card
        w1 = preset["weapon1"]
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + 118, fill="#0C1322", outline="#1E293B", width=1)
        # Accent left line
        self.canvas.create_line(px + 12, curr_y, px + 12, curr_y + 118, fill="#F59E0B", width=3)
        self.canvas.create_text(px + 22, curr_y + 14, text=f"PRIMARY • {w1.name}", anchor="w", fill="#FDE047", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(px + panel_w - 22, curr_y + 14, text="[F5 체크]", anchor="e", fill="#64748B", font=("Segoe UI", 8))

        w1_y = curr_y + 32
        for att, is_checked in zip(w1.attachments, w1.checked):
            box_bg = "#064E3B" if is_checked else "#1E293B"
            box_bd = "#10B981" if is_checked else "#475569"
            chk_sym = "✓" if is_checked else ""
            txt_col = "#F8FAFC" if is_checked else "#94A3B8"

            # Checkbox
            self.canvas.create_rectangle(px + 24, w1_y - 6, px + 36, w1_y + 6, fill=box_bg, outline=box_bd, width=1)
            if chk_sym:
                self.canvas.create_text(px + 30, w1_y, text=chk_sym, fill="#34D399", font=("Segoe UI", 8, "bold"))
            self.canvas.create_text(px + 44, w1_y, text=att, anchor="w", fill=txt_col, font=("Segoe UI", 9))
            w1_y += 19

        curr_y += 126

        # Weapon 2 Card
        w2 = preset["weapon2"]
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + 118, fill="#0C1322", outline="#1E293B", width=1)
        # Accent left line
        self.canvas.create_line(px + 12, curr_y, px + 12, curr_y + 118, fill="#38BDF8", width=3)
        self.canvas.create_text(px + 22, curr_y + 14, text=f"SECONDARY • {w2.name}", anchor="w", fill="#38BDF8", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(px + panel_w - 22, curr_y + 14, text="[F6 체크]", anchor="e", fill="#64748B", font=("Segoe UI", 8))

        w2_y = curr_y + 32
        for att, is_checked in zip(w2.attachments, w2.checked):
            box_bg = "#064E3B" if is_checked else "#1E293B"
            box_bd = "#10B981" if is_checked else "#475569"
            chk_sym = "✓" if is_checked else ""
            txt_col = "#F8FAFC" if is_checked else "#94A3B8"

            self.canvas.create_rectangle(px + 24, w2_y - 6, px + 36, w2_y + 6, fill=box_bg, outline=box_bd, width=1)
            if chk_sym:
                self.canvas.create_text(px + 30, w2_y, text=chk_sym, fill="#34D399", font=("Segoe UI", 8, "bold"))
            self.canvas.create_text(px + 44, w2_y, text=att, anchor="w", fill=txt_col, font=("Segoe UI", 9))
            w2_y += 19

        curr_y += 126

        # Consumables Section Card
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + 98, fill="#0C1322", outline="#1E293B", width=1)
        self.canvas.create_line(px + 12, curr_y, px + 12, curr_y + 98, fill="#10B981", width=3)
        self.canvas.create_text(px + 22, curr_y + 14, text="BATTLE QUOTA • 필수 비축 소모품", anchor="w", fill="#34D399", font=("Segoe UI", 9, "bold"))

        con_y = curr_y + 34
        for item in self.state.consumables[:4]:
            cur = item.current_count
            tgt = item.target_count
            is_full = cur >= tgt

            # Visual progress blocks: e.g. ■■■□
            filled = min(tgt, cur)
            empty = max(0, tgt - filled)
            blocks_str = "■" * filled + "□" * empty

            self.canvas.create_text(px + 24, con_y, text=f"• {item.name}", anchor="w", fill="#E2E8F0", font=("Segoe UI", 8))
            self.canvas.create_text(px + 160, con_y, text=blocks_str, anchor="w", fill="#10B981" if is_full else "#FBBF24", font=("Segoe UI", 7))
            self.canvas.create_text(px + panel_w - 24, con_y, text=f"{cur}/{tgt}", anchor="e", fill="#F8FAFC" if is_full else "#94A3B8", font=("Segoe UI", 8, "bold"))
            con_y += 15

        # Footer tip
        self.canvas.create_text(px + panel_w // 2, py + panel_h - 12, text="[TAB] 홀드 | [F8] OCR 토글 | [F7] 새 게임 리셋", fill="#64748B", font=("Segoe UI", 8))

    def draw_status_bar(self):
        """Top-left subtle status indicator"""
        if not self.loot_visible and not self.map_hud_visible and not self.map_pins_visible:
            ocr_flag = "ON" if self.ocr_enabled else "OFF"
            map_name = self.state.current_map_name.split()[0]
            txt = f"🛡️ BAN-SAFE OVERLAY V2.0 • [M] 전술지도({map_name}) | [TAB] 파밍가이드 | [~] 브리핑 | [F8] OCR({ocr_flag}) | [F10] 맵교체 | [F9] 종료"
            self.canvas.create_text(16, 16, text=txt, anchor="nw", fill="#475569", font=("Segoe UI", 8, "bold"))

    def draw_map_pins(self):
        """Draw high-contrast tactical pin markers directly over in-game map when M is pressed"""
        if not self.map_pins_visible:
            return

        map_size = int(self.screen_height * 0.94)
        map_top = int(self.screen_height * 0.03)
        map_left = int((self.screen_width - map_size) // 2)

        map_name = self.state.current_map_name
        map_info = self.state.current_map_info

        # Top Tactical Header Pill
        badge_w = 480
        badge_h = 34
        bx = self.screen_width // 2 - badge_w // 2
        by = map_top + 8

        # Shadow & Header
        self.canvas.create_rectangle(bx + 4, by + 4, bx + badge_w + 4, by + badge_h + 4, fill="#020617", outline="")
        self.canvas.create_rectangle(bx, by, bx + badge_w, by + badge_h, fill="#090E17", outline="#0284C7", width=1.5)
        self.canvas.create_oval(bx + 14, by + 13, bx + 22, by + 21, fill="#0284C7", outline="")
        self.canvas.create_text(
            bx + 30, by + 17,
            text=f"TACTICAL RADAR • {map_name} (8x8 km)",
            anchor="w", fill="#38BDF8", font=("Segoe UI", 9, "bold")
        )
        self.canvas.create_text(
            bx + badge_w - 14, by + 17,
            text="[M/ESC] 닫기 | [F10] 맵순환",
            anchor="e", fill="#94A3B8", font=("Segoe UI", 8)
        )

        # 1. Secret Rooms / Vaults (Pulsing Gold / Amber Pins)
        for room in map_info.get("secret_rooms", []):
            rx = map_left + int(room.get("x", 0.5) * map_size)
            ry = map_top + int(room.get("y", 0.5) * map_size)
            name = room.get("name", "비밀방")

            # Outer target crosshair ring
            self.canvas.create_oval(rx - 15, ry - 15, rx + 15, ry + 15, fill="", outline="#78350F", width=1)
            # Glowing core
            self.canvas.create_oval(rx - 11, ry - 11, rx + 11, ry + 11, fill="#92400E", outline="#FBBF24", width=2)
            self.canvas.create_text(rx, ry, text="🔑", font=("Segoe UI", 8))

            # Callout badge underneath
            text_w = max(54, len(name) * 11 + 10)
            self.canvas.create_rectangle(rx - text_w // 2, ry + 13, rx + text_w // 2, ry + 27, fill="#090E17", outline="#F59E0B", width=1)
            self.canvas.create_text(rx, ry + 20, text=name, fill="#FDE68A", font=("Segoe UI", 8, "bold"))

        # 2. Fixed Garages & Vehicle Spawns (Emerald / Green Pins)
        for v in map_info.get("vehicles", []):
            vx = map_left + int(v.get("x", 0.5) * map_size)
            vy = map_top + int(v.get("y", 0.5) * map_size)
            vtype = v.get("type", "차량")

            # Outer target crosshair ring
            self.canvas.create_oval(vx - 14, vy - 14, vx + 14, vy + 14, fill="", outline="#064E3B", width=1)
            # Glowing core
            self.canvas.create_oval(vx - 10, vy - 10, vx + 10, vy + 10, fill="#047857", outline="#34D399", width=2)
            self.canvas.create_text(vx, vy, text="🚗", font=("Segoe UI", 8))

            # Callout badge underneath
            text_w = max(56, len(vtype) * 10 + 10)
            self.canvas.create_rectangle(vx - text_w // 2, vy + 12, vx + text_w // 2, vy + 26, fill="#090E17", outline="#10B981", width=1)
            self.canvas.create_text(vx, vy + 19, text=vtype, fill="#A7F3D0", font=("Segoe UI", 7, "bold"))

    def draw_map_hud(self):
        """Map Vehicles & Secret Room locations panel (toggled with ~ or configured key)"""
        if not self.map_hud_visible:
            return

        panel_w = 410
        panel_h = 510
        px = 40
        py = 85

        # 1. Drop shadow
        self.canvas.create_rectangle(px + 6, py + 6, px + panel_w + 6, py + panel_h + 6, fill="#020617", outline="")

        # 2. Main Glass Card
        self.canvas.create_rectangle(px, py, px + panel_w, py + panel_h, fill="#090E17", outline="#1E293B", width=2)

        # 3. Header Titlebar
        self.canvas.create_rectangle(px, py, px + panel_w, py + 42, fill="#0F172A", outline="")
        self.canvas.create_line(px, py + 42, px + panel_w, py + 42, fill="#38BDF8", width=1.5)

        map_name = self.state.current_map_name
        map_info = self.state.current_map_info

        self.canvas.create_oval(px + 14, py + 18, px + 22, py + 26, fill="#38BDF8", outline="")
        self.canvas.create_text(px + 28, py + 21, text=f"INTELLIGENCE DOSSIER • {map_name}", anchor="w", fill="#38BDF8", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(px + panel_w - 14, py + 21, text="[F10] 맵변경", anchor="e", fill="#93C5FD", font=("Segoe UI", 8, "bold"))

        curr_y = py + 54

        # Description Card
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + 26, fill="#0D1526", outline="#1E3A8A", width=1)
        self.canvas.create_text(px + 20, curr_y + 13, text=map_info["desc"], anchor="w", fill="#94A3B8", font=("Segoe UI", 8))
        curr_y += 36

        # Section 1: Secret Rooms / Keys
        sec_h = 20 + len(map_info["secret_rooms"][:6]) * 32
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + sec_h, fill="#0C1322", outline="#1E293B", width=1)
        self.canvas.create_line(px + 12, curr_y, px + 12, curr_y + sec_h, fill="#F59E0B", width=3)

        key_label = "🔑 " + map_info["key_name"]
        self.canvas.create_text(px + 22, curr_y + 14, text=key_label, anchor="w", fill="#FBBF24", font=("Segoe UI", 9, "bold"))
        room_y = curr_y + 32

        for room in map_info["secret_rooms"][:6]:
            self.canvas.create_text(px + 26, room_y, text=f"▶ {room['name']}", anchor="w", fill="#FDE68A", font=("Segoe UI", 8, "bold"))
            self.canvas.create_text(px + 36, room_y + 14, text=room["loc"], anchor="w", fill="#94A3B8", font=("Segoe UI", 7))
            room_y += 30

        curr_y += sec_h + 12

        # Section 2: Vehicles & Spawns
        veh_h = 20 + len(map_info["vehicles"]) * 30
        self.canvas.create_rectangle(px + 12, curr_y, px + panel_w - 12, curr_y + veh_h, fill="#0C1322", outline="#1E293B", width=1)
        self.canvas.create_line(px + 12, curr_y, px + 12, curr_y + veh_h, fill="#10B981", width=3)

        self.canvas.create_text(px + 22, curr_y + 14, text="🚗 HIGH-VALUE VEHICLE & BOAT SPAWNS", anchor="w", fill="#34D399", font=("Segoe UI", 9, "bold"))
        veh_y = curr_y + 32

        for v in map_info["vehicles"]:
            self.canvas.create_text(px + 26, veh_y, text=f"• {v['type']}", anchor="w", fill="#A7F3D0", font=("Segoe UI", 8, "bold"))
            self.canvas.create_text(px + 36, veh_y + 13, text=v["loc"], anchor="w", fill="#64748B", font=("Segoe UI", 7))
            veh_y += 28

        # Footer
        self.canvas.create_text(px + panel_w // 2, py + panel_h - 12, text="[~] 키로 요약 닫기 | [M] 키를 누르면 게임 지도 위에 핀이 표시됩니다", fill="#64748B", font=("Segoe UI", 8))

    def draw_toast(self):
        if self.toast_msg and time.time() < self.toast_expire:
            cx = self.screen_width // 2
            ty = 90
            msg = self.toast_msg
            w = max(280, len(msg) * 11 + 48)
            x1, y1 = cx - w // 2, ty - 16
            x2, y2 = cx + w // 2, ty + 16

            # Drop shadow
            self.canvas.create_rectangle(x1 + 3, y1 + 3, x2 + 3, y2 + 3, fill="#020617", outline="")
            # Pill card
            self.canvas.create_rectangle(x1, y1, x2, y2, fill="#090E17", outline="#38BDF8", width=1.5)
            self.canvas.create_oval(x1 + 10, ty - 4, x1 + 18, ty + 4, fill="#38BDF8", outline="")
            self.canvas.create_text(cx + 6, ty, text=msg, fill="#F8FAFC", font=("Segoe UI", 9, "bold"))

    def update_ui(self):
        if not self.running:
            return
        self.canvas.delete("all")

        self.draw_crosshair()
        self.draw_grenade_hud()
        self.draw_bluezone_hud()
        self.draw_loot_hud()
        self.draw_map_hud()
        self.draw_map_pins()
        self.draw_status_bar()
        self.draw_toast()

        self.root.after(20, self.update_ui)

    def run(self, dry_run: bool = False):
        if dry_run:
            self.update_ui()
            self.running = False
            self.root.destroy()
            return
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.running = False


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "--test" in sys.argv
    app = PubgOverlayApp()
    app.run(dry_run=dry_run)

