"""
PUBG Convenience Overlay - Core Logic Layer
Pure Python logic for weapon presets, loot state, grenade timer, and bluezone phases.
No GUI or OS dependencies for testability and clean architecture.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os

@dataclass
class WeaponLoadout:
    name: str
    category: str  # AR, DMR, SR, SMG
    attachments: List[str]
    checked: List[bool] = field(default_factory=list)

    def __post_init__(self):
        if not self.checked or len(self.checked) != len(self.attachments):
            self.checked = [False] * len(self.attachments)

    def toggle_attachment(self, index: int):
        if 0 <= index < len(self.checked):
            self.checked[index] = not self.checked[index]

    def reset(self):
        self.checked = [False] * len(self.attachments)


@dataclass
class ConsumableItem:
    name: str
    target_count: int
    current_count: int = 0

    def add(self, delta: int = 1):
        self.current_count = max(0, self.current_count + delta)

    def reset(self):
        self.current_count = 0


DEFAULT_PRESETS = [
    {
        "name": "AR + DMR (국민 세팅: M416 + 드라구노프)",
        "weapon1": WeaponLoadout(
            name="M416 (AR)",
            category="AR",
            attachments=["보정기/소음기", "수직/하프 손잡이", "대용량 퀵드로우", "전술 개머리판", "조준경(레드도트/3배)"]
        ),
        "weapon2": WeaponLoadout(
            name="드라구노프 (DMR)",
            category="DMR",
            attachments=["소음기/보정기", "대용량 퀵드로우", "칙패드", "고배율(4배/6배)"]
        )
    },
    {
        "name": "7탄 조합 (베릴 M762 + SLR)",
        "weapon1": WeaponLoadout(
            name="베릴 M762 (AR)",
            category="AR",
            attachments=["보정기", "수직 손잡이", "대용량 퀵드로우", "조준경(레드도트)"]
        ),
        "weapon2": WeaponLoadout(
            name="SLR (DMR)",
            category="DMR",
            attachments=["보정기/소음기", "대용량 퀵드로우", "칙패드", "고배율(6배/8배)"]
        )
    },
    {
        "name": "5탄 기동 조합 (AUG / ACE + 미니14)",
        "weapon1": WeaponLoadout(
            name="AUG / ACE32",
            category="AR",
            attachments=["보정기", "수직/앵글 손잡이", "대용량 퀵드로우", "조준경"]
        ),
        "weapon2": WeaponLoadout(
            name="미니14 (DMR)",
            category="DMR",
            attachments=["보정기/소음기", "대용량 퀵드로우", "고배율(6배/8배)"]
        )
    },
    {
        "name": "근접/저격 (MP5K/Vector + Kar98k)",
        "weapon1": WeaponLoadout(
            name="MP5K / Vector (SMG)",
            category="SMG",
            attachments=["보정기", "수직손잡이", "대용량 탄창", "전술 개머리판", "레드도트"]
        ),
        "weapon2": WeaponLoadout(
            name="Kar98k / 모신나강 (SR)",
            category="SR",
            attachments=["소음기", "탄띠 / 칙패드", "고배율(6배/8배)"]
        )
    }
]

DEFAULT_CONSUMABLES = [
    ConsumableItem(name="구급상자", target_count=4),
    ConsumableItem(name="드링크/진통제", target_count=5),
    ConsumableItem(name="연막탄", target_count=4),
    ConsumableItem(name="수류탄", target_count=2),
    ConsumableItem(name="붕대", target_count=5),
]

BLUEZONE_PHASES = [
    {"phase": 1, "wait_sec": 300, "shrink_sec": 240, "desc": "1페이즈 (파밍 및 초기 이동)"},
    {"phase": 2, "wait_sec": 200, "shrink_sec": 160, "desc": "2페이즈 (외곽 진입)"},
    {"phase": 3, "wait_sec": 150, "shrink_sec": 120, "desc": "3페이즈 (요충지 확보)"},
    {"phase": 4, "wait_sec": 120, "shrink_sec": 90,  "desc": "4페이즈 (안전지대 압축)"},
    {"phase": 5, "wait_sec": 90,  "shrink_sec": 60,  "desc": "5페이즈 (후반 진입 전투)"},
    {"phase": 6, "wait_sec": 60,  "shrink_sec": 45,  "desc": "6페이즈 (자기장 데미지 급증)"},
    {"phase": 7, "wait_sec": 45,  "shrink_sec": 30,  "desc": "7페이즈 (파이널 서클)"},
    {"phase": 8, "wait_sec": 30,  "shrink_sec": 20,  "desc": "8페이즈 (최종 승부)"},
]

class GameStateManager:
    def __init__(self):
        self.presets = [
            {
                "name": p["name"],
                "weapon1": WeaponLoadout(p["weapon1"].name, p["weapon1"].category, list(p["weapon1"].attachments)),
                "weapon2": WeaponLoadout(p["weapon2"].name, p["weapon2"].category, list(p["weapon2"].attachments))
            }
            for p in DEFAULT_PRESETS
        ]
        self.current_preset_idx = 0
        self.consumables = [ConsumableItem(c.name, c.target_count) for c in DEFAULT_CONSUMABLES]
        
        # Crosshair state
        self.crosshair_enabled = True
        self.crosshair_style = "dot" # "dot", "cross", "circle_dot"
        self.crosshair_color = "#00FF66" # Neon green

        # Bluezone state
        self.bluezone_active = False
        self.current_phase_idx = 0
        self.bluezone_remaining_sec = 0
        self.bluezone_is_shrinking = False

        # Grenade timer state
        self.grenade_active = False
        self.grenade_remaining_sec = 0.0

    @property
    def current_preset(self) -> dict:
        return self.presets[self.current_preset_idx]

    def next_preset(self) -> dict:
        self.current_preset_idx = (self.current_preset_idx + 1) % len(self.presets)
        return self.current_preset

    def toggle_weapon1_attachment(self, index: int):
        self.current_preset["weapon1"].toggle_attachment(index)

    def toggle_weapon2_attachment(self, index: int):
        self.current_preset["weapon2"].toggle_attachment(index)

    def reset_loot_session(self):
        for preset in self.presets:
            preset["weapon1"].reset()
            preset["weapon2"].reset()
        for item in self.consumables:
            item.reset()

    # Bluezone controller
    def start_or_advance_bluezone(self):
        if not self.bluezone_active:
            self.bluezone_active = True
            self.current_phase_idx = 0
            self.bluezone_is_shrinking = False
            self.bluezone_remaining_sec = BLUEZONE_PHASES[0]["wait_sec"]
        else:
            if not self.bluezone_is_shrinking:
                # Switch to shrinking
                self.bluezone_is_shrinking = True
                self.bluezone_remaining_sec = BLUEZONE_PHASES[self.current_phase_idx]["shrink_sec"]
            else:
                # Advance to next phase
                if self.current_phase_idx + 1 < len(BLUEZONE_PHASES):
                    self.current_phase_idx += 1
                    self.bluezone_is_shrinking = False
                    self.bluezone_remaining_sec = BLUEZONE_PHASES[self.current_phase_idx]["wait_sec"]
                else:
                    self.bluezone_active = False

    def reset_bluezone(self):
        self.bluezone_active = False
        self.current_phase_idx = 0
        self.bluezone_remaining_sec = 0
        self.bluezone_is_shrinking = False

    def tick_bluezone(self, delta_sec: float = 1.0):
        if not self.bluezone_active:
            return
        self.bluezone_remaining_sec = max(0.0, self.bluezone_remaining_sec - delta_sec)
        if self.bluezone_remaining_sec <= 0:
            if not self.bluezone_is_shrinking:
                self.bluezone_is_shrinking = True
                self.bluezone_remaining_sec = BLUEZONE_PHASES[self.current_phase_idx]["shrink_sec"]
            else:
                if self.current_phase_idx + 1 < len(BLUEZONE_PHASES):
                    self.current_phase_idx += 1
                    self.bluezone_is_shrinking = False
                    self.bluezone_remaining_sec = BLUEZONE_PHASES[self.current_phase_idx]["wait_sec"]
                else:
                    self.bluezone_active = False

    # Grenade timer
    def trigger_grenade_cook(self):
        if self.grenade_active:
            # cancel if re-triggered
            self.grenade_active = False
            self.grenade_remaining_sec = 0.0
        else:
            self.grenade_active = True
            self.grenade_remaining_sec = 5.0

    def tick_grenade(self, delta_sec: float = 0.1) -> Optional[str]:
        """Returns sound event if any: 'danger', 'beep', 'throw', None"""
        if not self.grenade_active:
            return None
        prev_sec = self.grenade_remaining_sec
        self.grenade_remaining_sec = max(0.0, self.grenade_remaining_sec - delta_sec)
        
        event = None
        # Check boundary crossings
        if prev_sec > 2.0 >= self.grenade_remaining_sec:
            event = "danger"
        elif prev_sec > 1.0 >= self.grenade_remaining_sec:
            event = "throw_now"
        elif self.grenade_remaining_sec <= 0:
            self.grenade_active = False
            event = "detonated"
        return event

    def update_from_ocr_text(self, text: str) -> dict:
        """Parse recognized OCR text from PUBG inventory screen and auto-update loot state"""
        if not text:
            return {"attachments": [], "consumables": []}

        import re
        text_lower = text.lower()
        results = {"attachments": [], "consumables": []}

        # Check weapon 1 attachments
        w1 = self.current_preset["weapon1"]
        for idx, att in enumerate(w1.attachments):
            if w1.checked[idx]:
                continue
            kws = [k.lower() for k in re.findall(r'[a-zA-Z가-힣0-9]+', att) if len(k) >= 2]
            for kw in kws:
                if kw in text_lower:
                    w1.checked[idx] = True
                    results["attachments"].append(f"{w1.name}: {att}")
                    break

        # Check weapon 2 attachments
        w2 = self.current_preset["weapon2"]
        for idx, att in enumerate(w2.attachments):
            if w2.checked[idx]:
                continue
            kws = [k.lower() for k in re.findall(r'[a-zA-Z가-힣0-9]+', att) if len(k) >= 2]
            for kw in kws:
                if kw in text_lower:
                    w2.checked[idx] = True
                    results["attachments"].append(f"{w2.name}: {att}")
                    break

        # Check consumables count patterns e.g. '구급상자 3' or 'First Aid 4'
        consumable_patterns = {
            "구급상자": [r'구급상자\s*[:xX]?\s*(\d+)', r'first\s*aid\s*[:xX]?\s*(\d+)'],
            "드링크/진통제": [r'진통제\s*[:xX]?\s*(\d+)', r'드링크\s*[:xX]?\s*(\d+)', r'painkiller\s*[:xX]?\s*(\d+)', r'energy\s*[:xX]?\s*(\d+)'],
            "연막탄": [r'연막탄?\s*[:xX]?\s*(\d+)', r'smoke\s*[:xX]?\s*(\d+)'],
            "수류탄": [r'수류탄?\s*[:xX]?\s*(\d+)', r'frag\s*[:xX]?\s*(\d+)', r'grenade\s*[:xX]?\s*(\d+)'],
            "붕대": [r'붕대\s*[:xX]?\s*(\d+)', r'bandage\s*[:xX]?\s*(\d+)']
        }

        for c in self.consumables:
            patterns = consumable_patterns.get(c.name, [])
            for pat in patterns:
                m = re.search(pat, text_lower)
                if m:
                    try:
                        c.current_count = int(m.group(1))
                        results["consumables"].append(f"{c.name}: {c.current_count}개")
                        break
                    except ValueError:
                        pass

        return results

