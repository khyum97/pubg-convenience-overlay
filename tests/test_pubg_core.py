import unittest
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pubg_core import GameStateManager, WeaponLoadout, ConsumableItem

class TestPubgCore(unittest.TestCase):
    def setUp(self):
        self.sm = GameStateManager()

    def test_preset_initialization(self):
        self.assertGreaterEqual(len(self.sm.presets), 4)
        current = self.sm.current_preset
        self.assertIn("M416", current["weapon1"].name)
        self.assertEqual(len(current["weapon1"].attachments), len(current["weapon1"].checked))

    def test_next_preset(self):
        first_preset = self.sm.current_preset["name"]
        second = self.sm.next_preset()
        self.assertNotEqual(first_preset, second["name"])

    def test_toggle_attachment(self):
        w1 = self.sm.current_preset["weapon1"]
        self.assertFalse(w1.checked[0])
        self.sm.toggle_weapon1_attachment(0)
        self.assertTrue(w1.checked[0])
        self.sm.toggle_weapon1_attachment(0)
        self.assertFalse(w1.checked[0])

    def test_consumable_add_and_reset(self):
        first_aid = self.sm.consumables[0]
        self.assertEqual(first_aid.current_count, 0)
        first_aid.add(2)
        self.assertEqual(first_aid.current_count, 2)
        first_aid.add(-5)
        self.assertEqual(first_aid.current_count, 0)  # Cannot be negative
        first_aid.add(3)
        self.sm.reset_loot_session()
        self.assertEqual(first_aid.current_count, 0)

    def test_grenade_cook_timer(self):
        self.assertFalse(self.sm.grenade_active)
        self.sm.trigger_grenade_cook()
        self.assertTrue(self.sm.grenade_active)
        self.assertEqual(self.sm.grenade_remaining_sec, 5.0)

        # Tick 2.5s -> should remain 2.5s, no danger yet
        self.sm.tick_grenade(2.5)
        self.assertAlmostEqual(self.sm.grenade_remaining_sec, 2.5)

        # Tick 0.6s -> crosses 2.0s barrier
        evt = self.sm.tick_grenade(0.6)
        self.assertEqual(evt, "danger")

        # Tick 1.0s -> crosses 1.0s barrier
        evt = self.sm.tick_grenade(1.0)
        self.assertEqual(evt, "throw_now")

        # Tick 1.0s -> detonate and deactivate
        evt = self.sm.tick_grenade(1.0)
        self.assertEqual(evt, "detonated")
        self.assertFalse(self.sm.grenade_active)

    def test_bluezone_phases(self):
        self.assertFalse(self.sm.bluezone_active)
        self.sm.start_or_advance_bluezone()
        self.assertTrue(self.sm.bluezone_active)
        self.assertEqual(self.sm.current_phase_idx, 0)
        self.assertFalse(self.sm.bluezone_is_shrinking)
        self.assertEqual(self.sm.bluezone_remaining_sec, 300)

        # Advance to shrinking
        self.sm.start_or_advance_bluezone()
        self.assertTrue(self.sm.bluezone_is_shrinking)
        self.assertEqual(self.sm.bluezone_remaining_sec, 240)

        # Advance to phase 2
        self.sm.start_or_advance_bluezone()
        self.assertEqual(self.sm.current_phase_idx, 1)
        self.assertFalse(self.sm.bluezone_is_shrinking)

        self.sm.reset_bluezone()
        self.assertFalse(self.sm.bluezone_active)

    def test_ocr_parsing(self):
        w1 = self.sm.current_preset["weapon1"]
        self.assertFalse(w1.checked[0]) # 보정기

        sample_text = "인벤토리 보정기 수직 손잡이 구급상자 3 연막탄 2"
        res = self.sm.update_from_ocr_text(sample_text)

        self.assertTrue(w1.checked[0]) # 보정기 checked
        self.assertTrue(w1.checked[1]) # 수직손잡이 checked
        
        # Check consumables updated
        first_aid = self.sm.consumables[0] # 구급상자
        self.assertEqual(first_aid.current_count, 3)

        smoke = self.sm.consumables[2] # 연막탄
        self.assertEqual(smoke.current_count, 2)

if __name__ == "__main__":
    unittest.main()

