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

MAP_DATA = {
    "태이고 (Taego)": {
        "desc": "8x8km 대형 맵 (비밀의 방 열쇠 스폰)",
        "has_secret_room": True,
        "key_name": "비밀의 방 열쇠 (Secret Key)",
        "secret_rooms": [
            {"name": "스튜디오 남서쪽", "loc": "Studio 남서 삼거리 창고 (푸른 지붕)", "x": 0.28, "y": 0.65},
            {"name": "군부대 북쪽", "loc": "Army Camp 북측 삼거리 판잣집", "x": 0.72, "y": 0.26},
            {"name": "터미널 남동쪽", "loc": "Terminal 남동 산자락 건물", "x": 0.58, "y": 0.42},
            {"name": "호산 북동쪽", "loc": "Hosan 외곽 2층 단독 가옥", "x": 0.46, "y": 0.53},
            {"name": "송암 남서쪽", "loc": "Song Am 남서 해안 도로변 창고", "x": 0.32, "y": 0.36},
            {"name": "용택 북쪽", "loc": "Yong Taek 북쪽 언덕 철문 창고", "x": 0.64, "y": 0.67},
            {"name": "강릉 인근", "loc": "사찰 남쪽 계곡 바위 옆 건물", "x": 0.53, "y": 0.22},
            {"name": "공항 북서쪽", "loc": "활주로 북서 외곽 붉은 지붕 창고", "x": 0.81, "y": 0.77}
        ],
        "vehicles": [
            {"type": "포니 쿠페 차고", "loc": "호산(Hosan) 시내 3거리 차고지", "x": 0.44, "y": 0.51},
            {"type": "쿠페 고정 차고", "loc": "터미널(Terminal) 진입로 차고지", "x": 0.55, "y": 0.41},
            {"type": "지프/픽업 차고", "loc": "스튜디오(Studio) 정문 삼거리", "x": 0.30, "y": 0.63},
            {"type": "해안선 보트", "loc": "송암(Song Am) 남쪽 선착장 & 모래사장", "x": 0.31, "y": 0.42}
        ]
    },
    "데스턴 (Deston)": {
        "desc": "8x8km 대도시 맵 (보안 키카드 & 드론방)",
        "has_secret_room": True,
        "key_name": "보안 키카드 (Security Keycard)",
        "secret_rooms": [
            {"name": "립턴 고층빌딩", "loc": "Ripton 시내 초고층 빌딩 내부 보안실", "x": 0.68, "y": 0.67},
            {"name": "콘서트홀 뒤편", "loc": "Concert 무대 뒤편 특수 보안 컨테이너", "x": 0.52, "y": 0.48},
            {"name": "수력발전소 댐", "loc": "댐 상부 제어실 보안실", "x": 0.24, "y": 0.35},
            {"name": "아레나 지하", "loc": "Arena 경기장 지하 통제 구역", "x": 0.48, "y": 0.24},
            {"name": "풍력발전 남쪽", "loc": "풍력단지 남쪽 단독 연구동", "x": 0.78, "y": 0.32},
            {"name": "물류단지 창고", "loc": "중앙 대형 물류창고 2층 통제실", "x": 0.38, "y": 0.58}
        ],
        "vehicles": [
            {"type": "에어보트 스폰", "loc": "늪지대(Swamp) 전역 및 수로 교차로", "x": 0.56, "y": 0.78},
            {"type": "기둥 보안차량", "loc": "Ripton 경찰서 및 보안센터 차고", "x": 0.64, "y": 0.62},
            {"type": "고속 픽업트럭", "loc": "고속도로 톨게이트 및 주요 주유소", "x": 0.38, "y": 0.70}
        ]
    },
    "론도 (Rondo)": {
        "desc": "8x8km 동양풍 맵 (금고실 열쇠 & 테일게이트)",
        "has_secret_room": True,
        "key_name": "비밀 금고 열쇠 (Vault Key)",
        "secret_rooms": [
            {"name": "자등 도심 금고", "loc": "Jadeng 중앙 빌딩 지하 특수 금고", "x": 0.46, "y": 0.52},
            {"name": "연천 사찰 금고", "loc": "Yeoncheon 사원 본당 뒤편 석조실", "x": 0.34, "y": 0.38},
            {"name": "공장 관리동", "loc": "대형 조립라인 2층 보안 금고실", "x": 0.51, "y": 0.30},
            {"name": "린쟝 수상가옥", "loc": "강변 목조가옥 중앙 잠긴 철문", "x": 0.58, "y": 0.62},
            {"name": "테스트 트랙", "loc": "서킷 패독 1호 지하 창고", "x": 0.72, "y": 0.44}
        ],
        "vehicles": [
            {"type": "블랑 SUV 차고", "loc": "Jadeng 고속화도로 나들목 차고", "x": 0.48, "y": 0.50},
            {"type": "우라우스 트럭", "loc": "Factory 정문 주차장 & 물류 터미널", "x": 0.53, "y": 0.32},
            {"type": "버기/오토바이", "loc": "중앙 평원 삼거리 주유소", "x": 0.60, "y": 0.42}
        ]
    },
    "에란겔 (Erangel)": {
        "desc": "8x8km 오리지널 맵 (지하실 & 고정 차고지)",
        "has_secret_room": False,
        "key_name": "지하실 나무 판자 (사격 파괴)",
        "secret_rooms": [
            {"name": "포친키 지하실", "loc": "Pochinki 남서쪽 파란 슬레이트 단독주택", "x": 0.48, "y": 0.62},
            {"name": "야스나야 북서", "loc": "Yasnaya 북서 언덕 2층 벽돌집", "x": 0.62, "y": 0.35},
            {"name": "밀타 서쪽", "loc": "Mylta에서 밀베 다리 가는 삼거리 가옥", "x": 0.70, "y": 0.68},
            {"name": "로족 언덕", "loc": "Rozhok 수영장 남쪽 고지대 가옥", "x": 0.50, "y": 0.40},
            {"name": "서버노 남쪽", "loc": "Severny 진입로 꿀집 지하실", "x": 0.42, "y": 0.16}
        ],
        "vehicles": [
            {"type": "다시아 100% 차고", "loc": "야스나야 남쪽 삼거리 / 로족 삼거리 차고", "x": 0.51, "y": 0.42},
            {"type": "포친키 차고", "loc": "포친키 북동쪽 차고 딸린 2층집", "x": 0.49, "y": 0.59},
            {"type": "밀베 다리 차고", "loc": "페리피어(Ferry Pier) 삼거리 차고", "x": 0.36, "y": 0.78},
            {"type": "보트 고정 스폰", "loc": "밀타 파워 해안가 및 소스노브카 남쪽 섬", "x": 0.85, "y": 0.56}
        ]
    },
    "미라마 (Miramar)": {
        "desc": "8x8km 사막 맵 (특수 차량 & 황금 미라도)",
        "has_secret_room": False,
        "key_name": "특수 잠금 해제 구역",
        "secret_rooms": [
            {"name": "하시엔다 차고", "loc": "Hacienda del Patron 1층 내부 차고", "x": 0.55, "y": 0.38},
            {"name": "로스 레오네스", "loc": "Los Leones 남부 대형 공사장 창고", "x": 0.62, "y": 0.66},
            {"name": "오아시스 은신처", "loc": "북단 Oasis 계곡 바위 틈 텐트", "x": 0.52, "y": 0.08}
        ],
        "vehicles": [
            {"type": "★ 황금 미라도", "loc": "하시엔다(Hacienda) 대저택 내부 차고", "x": 0.55, "y": 0.38},
            {"type": "픽업트럭 고정 차고", "loc": "페카도(Pecado) 카지노 뒤편 차고지", "x": 0.47, "y": 0.52},
            {"type": "버기/미라도 스폰", "loc": "엘 아자하르(El Azahar) 메인 도로변", "x": 0.74, "y": 0.45}
        ]
    },
    "사녹 (Sanhok)": {
        "desc": "4x4km 정글 맵 (동굴 보트 & 루트 트럭/사원)",
        "has_secret_room": True,
        "key_name": "특수 파밍 요충지 (동굴/유적/지하)",
        "secret_rooms": [
            {"name": "동굴(Cave) 해식동", "loc": "원형 해식동굴 내부 수로 & 고급 루팅", "x": 0.72, "y": 0.74},
            {"name": "루인스(Ruins) 제단", "loc": "사원 중앙 지하 제단실 및 석조 갱도", "x": 0.35, "y": 0.58},
            {"name": "부트캠프(Bootcamp)", "loc": "중앙 Y자 건물 옥상 및 지하 통로", "x": 0.52, "y": 0.44},
            {"name": "파라다이스 리조트", "loc": "중앙 마당 본관 2층 고급 루팅 구역", "x": 0.68, "y": 0.32},
            {"name": "채석장(Quarry) 갱도", "loc": "채석장 절벽 아래 은신처 컨테이너", "x": 0.64, "y": 0.56}
        ],
        "vehicles": [
            {"type": "동굴 제트스키/보트", "loc": "Cave 내부 수로 100% 확정 보트/아쿠아레일", "x": 0.72, "y": 0.75},
            {"type": "파이난 강변 나루터", "loc": "Pai Nan 다리 인근 강변 보트", "x": 0.42, "y": 0.60},
            {"type": "부트캠프 남쪽 차고", "loc": "삼거리 로니(Rony)/오토바이 스폰", "x": 0.51, "y": 0.48},
            {"type": "하틴(Ha Tinh) 다리", "loc": "철교 진입로 툭툭이/오토바이", "x": 0.38, "y": 0.24}
        ]
    }
}

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
        # Map info state
        self.map_names = list(MAP_DATA.keys())
        self.current_map_idx = 0

    @property
    def current_map_name(self) -> str:
        return self.map_names[self.current_map_idx]

    @property
    def current_map_info(self) -> dict:
        return MAP_DATA[self.current_map_name]

    def next_map(self) -> str:
        self.current_map_idx = (self.current_map_idx + 1) % len(self.map_names)
        return self.current_map_name

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

