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
        self.running = True

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
                "exit_app": "VK_F9"
            },
            "settings": {
                "loot_hud_hold_mode": True,
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
        cy = self.screen_height // 2 + 120
        rem = self.state.grenade_remaining_sec

        # Background badge
        w, h = 220, 56
        x1, y1 = cx - w // 2, cy - h // 2
        x2, y2 = cx + w // 2, cy + h // 2
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#111116", outline="#FF4444", width=2)

        # Progress bar
        ratio = max(0.0, min(1.0, rem / 5.0))
        bar_w = int((w - 20) * ratio)
        bar_col = "#00FF66" if rem > 2.0 else ("#FF9900" if rem > 1.0 else "#FF2222")
        self.canvas.create_rectangle(x1 + 10, y2 - 12, x1 + 10 + bar_w, y2 - 6, fill=bar_col, outline="")

        # Text
        status_txt = "💣 수류탄 쿠킹 중!" if rem > 1.5 else "⚠️ 지금 던지세요! (THROW)"
        self.canvas.create_text(cx, cy - 8, text=f"{status_txt} {rem:.1f}s", fill="#FFFFFF", font=("Segoe UI", 12, "bold"))

    def draw_bluezone_hud(self):
        if not self.state.bluezone_active:
            return
        cx = self.screen_width // 2
        top_y = 35
        phase_info = BLUEZONE_PHASES[self.state.current_phase_idx]
        rem = int(self.state.bluezone_remaining_sec)
        mm, ss = divmod(rem, 60)
        time_str = f"{mm:02d}:{ss:02d}"

        mode_str = "축소 진행 중" if self.state.bluezone_is_shrinking else "대기 시간"
        mode_col = "#FF5555" if self.state.bluezone_is_shrinking else "#00FFCC"

        w, h = 320, 48
        x1, y1 = cx - w // 2, top_y
        x2, y2 = cx + w // 2, top_y + h

        # Glass panel
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#0F111A", outline=mode_col, width=2)
        txt = f"[{phase_info['phase']}페이즈 {mode_str}] {time_str}"
        self.canvas.create_text(cx, top_y + 24, text=txt, fill="#FFFFFF", font=("Segoe UI", 13, "bold"))

    def draw_loot_hud(self):
        """Loot & Attachment Checklist HUD rendered when TAB (or configured key) is pressed"""
        if not self.loot_visible:
            return

        # Position at top right
        panel_w = 340
        panel_h = 490
        px = self.screen_width - panel_w - 40
        py = 90

        # Background panel (Dark glass card)
        self.canvas.create_rectangle(px, py, px + panel_w, py + panel_h, fill="#0E121B", outline="#2F3B52", width=2)

        # Header
        self.canvas.create_rectangle(px, py, px + panel_w, py + 38, fill="#1B2232", outline="")
        preset = self.state.current_preset
        self.canvas.create_text(px + 15, py + 19, text="📦 파밍 가이드 & 부착물 체크", anchor="w", fill="#00FFCC", font=("Segoe UI", 11, "bold"))
        self.canvas.create_text(px + panel_w - 15, py + 19, text="[F4] 변경", anchor="e", fill="#8899AA", font=("Segoe UI", 9))

        curr_y = py + 48

        # Current Preset Name
        self.canvas.create_text(px + 15, curr_y, text=f"• 세팅: {preset['name']}", anchor="w", fill="#FFFFFF", font=("Segoe UI", 10, "bold"))
        curr_y += 24

        # Weapon 1 Attachments
        w1 = preset["weapon1"]
        self.canvas.create_text(px + 15, curr_y, text=f"🔫 {w1.name}", anchor="w", fill="#FFB703", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(px + panel_w - 15, curr_y, text="[F5] 체크", anchor="e", fill="#778899", font=("Segoe UI", 9))
        curr_y += 18

        for idx, (att, is_checked) in enumerate(zip(w1.attachments, w1.checked)):
            chk_icon = "[✔]" if is_checked else "[ ]"
            color = "#00FF66" if is_checked else "#D0D6E0"
            self.canvas.create_text(px + 25, curr_y, text=f"{chk_icon} {att}", anchor="w", fill=color, font=("Segoe UI", 9))
            curr_y += 18

        curr_y += 6

        # Weapon 2 Attachments
        w2 = preset["weapon2"]
        self.canvas.create_text(px + 15, curr_y, text=f"🎯 {w2.name}", anchor="w", fill="#00D2FF", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(px + panel_w - 15, curr_y, text="[F6] 체크", anchor="e", fill="#778899", font=("Segoe UI", 9))
        curr_y += 18

        for idx, (att, is_checked) in enumerate(zip(w2.attachments, w2.checked)):
            chk_icon = "[✔]" if is_checked else "[ ]"
            color = "#00FF66" if is_checked else "#D0D6E0"
            self.canvas.create_text(px + 25, curr_y, text=f"{chk_icon} {att}", anchor="w", fill=color, font=("Segoe UI", 9))
            curr_y += 18

        curr_y += 10
        # Divider
        self.canvas.create_line(px + 15, curr_y, px + panel_w - 15, curr_y, fill="#243046")
        curr_y += 10

        # Consumables Target Section
        self.canvas.create_text(px + 15, curr_y, text="🩹 필수 회복약 & 투척무기 목표치", anchor="w", fill="#FFAA00", font=("Segoe UI", 10, "bold"))
        curr_y += 20

        for item in self.state.consumables:
            txt = f"• {item.name}: 목표 {item.target_count}개"
            self.canvas.create_text(px + 25, curr_y, text=txt, anchor="w", fill="#E2E8F0", font=("Segoe UI", 9))
            curr_y += 18

        # Footer tips
        self.canvas.create_line(px + 15, py + panel_h - 32, px + panel_w - 15, py + panel_h - 32, fill="#243046")
        tip_txt = "TAB 누르는 동안 표시됨 | [F7] 새 게임 리셋"
        self.canvas.create_text(px + panel_w // 2, py + panel_h - 16, text=tip_txt, fill="#708090", font=("Segoe UI", 8))

    def draw_status_bar(self):
        """Top-left subtle status indicator"""
        # Shows when TAB is not held, as a minimal watermark guide
        if not self.loot_visible:
            txt = "[PUBG HUD] TAB:파밍체커 | F1:조준점 | F2:자기장 | F3:수류탄 | F4:총기프리셋 | F9:종료"
            self.canvas.create_text(15, 15, text=txt, anchor="nw", fill="#445566", font=("Segoe UI", 8))

    def update_ui(self):
        if not self.running:
            return
        self.canvas.delete("all")

        self.draw_crosshair()
        self.draw_grenade_hud()
        self.draw_bluezone_hud()
        self.draw_loot_hud()
        self.draw_status_bar()

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

