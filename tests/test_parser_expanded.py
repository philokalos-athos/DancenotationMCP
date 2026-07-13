"""Tests for the expanded phrase parser vocabulary (324 ACTION_PATTERNS)."""
from __future__ import annotations

import unittest

from dancenotation_mcp.planning.phrase_parser import parse_phrase


class BalletTermsTests(unittest.TestCase):
    """Ballet vocabulary maps to correct symbol_ids."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_plie(self):
        step = self._first("plié")
        self.assertEqual(step["symbol_id"], "support.plie")
        self.assertEqual(step["action"], "support")

    def test_releve(self):
        step = self._first("relevé")
        self.assertEqual(step["symbol_id"], "support.releve")
        self.assertEqual(step["action"], "support")

    def test_tendu_forward(self):
        step = self._first("tendu forward")
        self.assertEqual(step["symbol_id"], "gesture.leg")
        self.assertEqual(step["direction"], "forward")

    def test_grand_jete(self):
        step = self._first("grand jeté")
        self.assertEqual(step["symbol_id"], "jump.large")
        self.assertEqual(step["action"], "jump")

    def test_pirouette_right(self):
        step = self._first("pirouette right")
        self.assertEqual(step["symbol_id"], "turn.full")
        self.assertEqual(step["direction"], "right")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 360)

    def test_chaine(self):
        step = self._first("chaîné")
        self.assertEqual(step["symbol_id"], "turn.half")
        self.assertEqual(step["action"], "turn")

    def test_assemble(self):
        step = self._first("assemblé")
        self.assertEqual(step["symbol_id"], "jump.assemble")

    def test_sissonne(self):
        step = self._first("sissonne")
        self.assertEqual(step["symbol_id"], "jump.sissonne")

    def test_arabesque(self):
        step = self._first("arabesque")
        self.assertEqual(step["symbol_id"], "gesture.leg")

    def test_battement(self):
        step = self._first("battement")
        self.assertEqual(step["symbol_id"], "gesture.leg")

    def test_developpe(self):
        step = self._first("développé")
        self.assertEqual(step["symbol_id"], "gesture.leg")

    def test_fouette(self):
        step = self._first("fouetté")
        self.assertEqual(step["symbol_id"], "turn.full")

    def test_glissade(self):
        step = self._first("glissade")
        self.assertEqual(step["symbol_id"], "travel.glide")
        self.assertEqual(step["action"], "travel")

    def test_pas_de_bourree(self):
        step = self._first("pas de bourrée")
        self.assertEqual(step["symbol_id"], "travel.chasse")

    def test_changement(self):
        step = self._first("changement")
        self.assertEqual(step["symbol_id"], "jump.small")

    def test_entrechat(self):
        step = self._first("entrechat")
        self.assertEqual(step["symbol_id"], "jump.small")

    def test_cabriole(self):
        step = self._first("cabriole")
        self.assertEqual(step["symbol_id"], "jump.large")

    def test_port_de_bras(self):
        step = self._first("port de bras")
        self.assertEqual(step["symbol_id"], "gesture.arm")

    def test_soutenu(self):
        step = self._first("soutenu")
        self.assertEqual(step["symbol_id"], "turn.full")

    def test_fondu(self):
        step = self._first("fondu")
        self.assertEqual(step["symbol_id"], "support.lower")


class ModernTermsTests(unittest.TestCase):
    """Modern/contemporary dance vocabulary."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_contract_torso(self):
        step = self._first("contract torso")
        self.assertEqual(step["symbol_id"], "body.contract")
        self.assertEqual(step["body_part"], "torso")

    def test_body_release(self):
        step = self._first("body release")
        self.assertEqual(step["symbol_id"], "body.release")
        self.assertEqual(step["action"], "body")

    def test_spiral(self):
        step = self._first("spiral")
        self.assertEqual(step["symbol_id"], "body.tilt")
        self.assertEqual(step["action"], "body")

    def test_fall_to_floor(self):
        step = self._first("fall to floor")
        self.assertEqual(step["symbol_id"], "floor.fall")
        self.assertEqual(step["action"], "floor")

    def test_body_wave(self):
        step = self._first("body wave")
        self.assertEqual(step["symbol_id"], "body.bend")
        self.assertEqual(step["action"], "sequential")

    def test_contraction(self):
        step = self._first("contraction")
        self.assertEqual(step["symbol_id"], "body.contract")

    def test_tilt(self):
        step = self._first("tilt")
        self.assertEqual(step["symbol_id"], "body.tilt")

    def test_floor_roll(self):
        step = self._first("floor roll")
        self.assertEqual(step["symbol_id"], "floor.roll")

    def test_collapse(self):
        step = self._first("collapse")
        self.assertEqual(step["symbol_id"], "floor.fall")

    def test_melt_to_floor(self):
        step = self._first("melt to floor")
        self.assertEqual(step["symbol_id"], "floor.fall")

    def test_arch(self):
        step = self._first("arch")
        self.assertEqual(step["symbol_id"], "body.stretch")

    def test_curve(self):
        step = self._first("curve")
        self.assertEqual(step["symbol_id"], "body.bend")

    def test_rise_from_floor(self):
        step = self._first("rise from floor")
        self.assertEqual(step["symbol_id"], "support.rise")


class EffortLMATests(unittest.TestCase):
    """Effort/LMA terms produce correct effort modifiers."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_punch_forward(self):
        step = self._first("punch forward")
        self.assertEqual(step["symbol_id"], "gesture.arm")
        self.assertEqual(step["direction"], "forward")
        effort = step["modifiers"]["effort"]
        self.assertEqual(effort["weight"], "strong")
        self.assertEqual(effort["time"], "sudden")
        self.assertEqual(effort["space"], "direct")

    def test_float_high(self):
        step = self._first("float high")
        effort = step["modifiers"]["effort"]
        self.assertEqual(effort["weight"], "light")
        self.assertEqual(effort["time"], "sustained")
        self.assertEqual(effort["flow"], "free")

    def test_slash_right(self):
        step = self._first("slash right")
        self.assertEqual(step["direction"], "right")
        effort = step["modifiers"]["effort"]
        self.assertEqual(effort["weight"], "strong")
        self.assertEqual(effort["space"], "flexible")

    def test_wring_hands(self):
        step = self._first("wring hands")
        effort = step["modifiers"]["effort"]
        self.assertEqual(effort["weight"], "strong")
        self.assertEqual(effort["time"], "sustained")
        self.assertEqual(effort["space"], "flexible")

    def test_flick(self):
        step = self._first("flick")
        effort = step["modifiers"]["effort"]
        self.assertEqual(effort["weight"], "light")
        self.assertEqual(effort["time"], "sudden")

    def test_thrust(self):
        step = self._first("thrust")
        self.assertEqual(step["symbol_id"], "gesture.arm")

    def test_gliding_effort(self):
        step = self._first("gliding forward")
        effort = step["modifiers"]["effort"]
        self.assertEqual(effort["weight"], "light")
        self.assertEqual(effort["space"], "direct")


class RotationDegreesTests(unittest.TestCase):
    """Turn terms produce correct rotation_degrees modifiers."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_quarter_turn(self):
        step = self._first("quarter turn")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 90)
        self.assertEqual(step["action"], "turn")

    def test_half_turn(self):
        step = self._first("half turn")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 180)

    def test_full_turn(self):
        step = self._first("full turn")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 360)

    def test_double_turn(self):
        step = self._first("double turn")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 720)

    def test_triple_turn(self):
        step = self._first("triple turn")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 1080)

    def test_three_quarter_turn(self):
        step = self._first("three quarter turn")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 270)

    def test_pirouette_has_360(self):
        step = self._first("pirouette")
        self.assertEqual(step["modifiers"]["rotation_degrees"], 360)


class BodyWordsTests(unittest.TestCase):
    """Expanded body words resolve to correct body_part values."""

    def _body(self, prompt: str) -> str:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]["body_part"]

    def test_left_shoulder(self):
        self.assertEqual(self._body("step left shoulder"), "left_shoulder")

    def test_right_elbow(self):
        self.assertEqual(self._body("reach right elbow"), "right_elbow")

    def test_left_knee(self):
        self.assertEqual(self._body("step left knee"), "left_knee")

    def test_neck(self):
        self.assertEqual(self._body("gesture neck"), "neck")

    def test_upper_back(self):
        self.assertEqual(self._body("gesture upper back"), "upper_spine")

    def test_lower_back(self):
        self.assertEqual(self._body("gesture lower back"), "lower_spine")

    def test_pelvis(self):
        self.assertEqual(self._body("step pelvis"), "pelvis")

    def test_left_wrist(self):
        self.assertEqual(self._body("gesture left wrist"), "left_wrist")

    def test_right_ankle(self):
        self.assertEqual(self._body("step right ankle"), "right_ankle")

    def test_left_hip(self):
        self.assertEqual(self._body("step left hip"), "left_hip")

    def test_whole_body(self):
        self.assertEqual(self._body("gesture whole body"), "whole_body")

    def test_entire_body(self):
        self.assertEqual(self._body("gesture entire body"), "whole_body")

    def test_left_fingers(self):
        self.assertEqual(self._body("gesture left fingers"), "left_fingers")

    def test_right_toes(self):
        self.assertEqual(self._body("step right toes"), "right_toes")


class TimeSignatureTests(unittest.TestCase):
    """Expanded time signatures parse to correct symbol_ids and beat counts."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_5_4(self):
        step = self._first("5/4")
        self.assertEqual(step["symbol_id"], "music.time.5_4")
        self.assertEqual(step["action"], "meter")
        self.assertTrue(step["modifiers"]["measure_header"])

    def test_7_8(self):
        step = self._first("7/8")
        self.assertEqual(step["symbol_id"], "music.time.7_8")

    def test_6_8(self):
        step = self._first("6/8")
        self.assertEqual(step["symbol_id"], "music.time.6_8")

    def test_5_8(self):
        step = self._first("5/8")
        self.assertEqual(step["symbol_id"], "music.time.5_8")

    def test_9_8(self):
        step = self._first("9/8")
        self.assertEqual(step["symbol_id"], "music.time.9_8")

    def test_12_8(self):
        step = self._first("12/8")
        self.assertEqual(step["symbol_id"], "music.time.12_8")

    def test_generic_time_signature(self):
        """Any N/M time signature should be recognized via the regex fallback."""
        step = self._first("11/8")
        self.assertEqual(step["symbol_id"], "music.time.11_8")
        self.assertEqual(step["action"], "meter")

    def test_original_signatures_still_work(self):
        for sig, sym in [("2/4", "music.time.2_4"), ("3/4", "music.time.3_4"), ("4/4", "music.time.4_4")]:
            step = self._first(sig)
            self.assertEqual(step["symbol_id"], sym, f"Failed for {sig}")


class MultiBodyPatternsTests(unittest.TestCase):
    """Multi-body patterns expand to correct body_part lists."""

    def _bodies(self, prompt: str) -> list[str]:
        plan = parse_phrase(prompt)
        return [s["body_part"] for s in plan["steps"]]

    def test_both_shoulders(self):
        bodies = self._bodies("step both shoulders")
        self.assertEqual(bodies, ["left_shoulder", "right_shoulder"])

    def test_both_knees(self):
        bodies = self._bodies("step both knees")
        self.assertEqual(bodies, ["left_knee", "right_knee"])

    def test_both_wrists(self):
        bodies = self._bodies("gesture both wrists")
        self.assertEqual(bodies, ["left_wrist", "right_wrist"])

    def test_both_elbows(self):
        bodies = self._bodies("gesture both elbows")
        self.assertEqual(bodies, ["left_elbow", "right_elbow"])

    def test_both_hips(self):
        bodies = self._bodies("step both hips")
        self.assertEqual(bodies, ["left_hip", "right_hip"])

    def test_both_ankles(self):
        bodies = self._bodies("step both ankles")
        self.assertEqual(bodies, ["left_ankle", "right_ankle"])

    def test_original_both_arms_still_works(self):
        bodies = self._bodies("gesture both arms")
        self.assertEqual(bodies, ["left_arm", "right_arm"])

    def test_original_both_legs_still_works(self):
        bodies = self._bodies("step both legs")
        self.assertEqual(bodies, ["left_leg", "right_leg"])


class StagePositionTests(unittest.TestCase):
    """Stage position terms are recognized as actions."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_downstage_left(self):
        step = self._first("downstage left")
        self.assertEqual(step["action"], "stage")
        self.assertEqual(step["symbol_id"], "path.straight")

    def test_center_stage(self):
        step = self._first("center stage")
        self.assertEqual(step["action"], "stage")
        self.assertEqual(step["symbol_id"], "path.straight")

    def test_upstage_right(self):
        step = self._first("upstage right")
        self.assertEqual(step["action"], "stage")
        self.assertEqual(step["symbol_id"], "path.straight")

    def test_downstage_center(self):
        step = self._first("downstage center")
        self.assertEqual(step["action"], "stage")

    def test_upstage_left(self):
        step = self._first("upstage left")
        self.assertEqual(step["action"], "stage")

    def test_stage_left(self):
        step = self._first("stage left")
        self.assertEqual(step["action"], "stage")

    def test_stage_right(self):
        step = self._first("stage right")
        self.assertEqual(step["action"], "stage")


class RetentionTermsTests(unittest.TestCase):
    """Retention terms produce correct retention modifiers."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_hold_position(self):
        step = self._first("hold position")
        self.assertEqual(step["symbol_id"], "pin.hold")
        self.assertEqual(step["action"], "retention")
        self.assertEqual(step["modifiers"]["retention"], "hold")

    def test_release_position(self):
        step = self._first("release position")
        self.assertEqual(step["symbol_id"], "pin.hold")
        self.assertEqual(step["modifiers"]["retention"], "release")

    def test_freeze(self):
        step = self._first("freeze")
        self.assertEqual(step["symbol_id"], "pin.hold")
        self.assertEqual(step["modifiers"]["retention"], "hold")

    def test_stillness(self):
        step = self._first("stillness")
        self.assertEqual(step["symbol_id"], "pin.hold")

    def test_maintain(self):
        step = self._first("maintain")
        self.assertEqual(step["symbol_id"], "pin.hold")


class ContactTermsTests(unittest.TestCase):
    """Contact terms map to surface.contact."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_touch(self):
        step = self._first("touch")
        self.assertEqual(step["symbol_id"], "surface.contact")
        self.assertEqual(step["action"], "contact")

    def test_grasp(self):
        step = self._first("grasp")
        self.assertEqual(step["symbol_id"], "surface.contact")

    def test_embrace(self):
        step = self._first("embrace")
        self.assertEqual(step["symbol_id"], "surface.contact")

    def test_grip(self):
        step = self._first("grip")
        self.assertEqual(step["symbol_id"], "surface.contact")

    def test_clasp(self):
        step = self._first("clasp")
        self.assertEqual(step["symbol_id"], "surface.contact")


class FlexionTermsTests(unittest.TestCase):
    """Flexion terms map to flexion.knee."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_bend_knee(self):
        step = self._first("bend knee")
        self.assertEqual(step["symbol_id"], "flexion.knee")
        self.assertEqual(step["action"], "flexion")

    def test_flex_hip(self):
        step = self._first("flex hip")
        self.assertEqual(step["symbol_id"], "flexion.knee")
        self.assertEqual(step["action"], "flexion")

    def test_straighten_knee(self):
        step = self._first("straighten knee")
        self.assertEqual(step["symbol_id"], "flexion.knee")

    def test_flex_elbow(self):
        step = self._first("flex elbow")
        self.assertEqual(step["symbol_id"], "flexion.knee")

    def test_extend_knee(self):
        step = self._first("extend knee")
        self.assertEqual(step["symbol_id"], "flexion.knee")

    def test_flex_foot(self):
        step = self._first("flex foot")
        self.assertEqual(step["symbol_id"], "flexion.knee")

    def test_extension(self):
        step = self._first("extension")
        self.assertEqual(step["symbol_id"], "flexion.knee")

    def test_bend_knees(self):
        step = self._first("bend knees")
        self.assertEqual(step["symbol_id"], "flexion.knee")


class TravelTermsTests(unittest.TestCase):
    """Travel terms map to correct travel symbol_ids."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_run_forward(self):
        step = self._first("run forward")
        self.assertEqual(step["symbol_id"], "travel.run")
        self.assertEqual(step["action"], "travel")
        self.assertEqual(step["direction"], "forward")

    def test_skip(self):
        step = self._first("skip")
        self.assertEqual(step["symbol_id"], "travel.walk")
        self.assertEqual(step["action"], "travel")

    def test_gallop(self):
        step = self._first("gallop")
        self.assertEqual(step["symbol_id"], "travel.run")
        self.assertEqual(step["action"], "travel")

    def test_chasse(self):
        step = self._first("chassé")
        self.assertEqual(step["symbol_id"], "travel.chasse")
        self.assertEqual(step["action"], "travel")

    def test_march(self):
        step = self._first("march")
        self.assertEqual(step["symbol_id"], "travel.walk")

    def test_crawl(self):
        step = self._first("crawl")
        self.assertEqual(step["symbol_id"], "travel.walk")

    def test_shuffle(self):
        step = self._first("shuffle")
        self.assertEqual(step["symbol_id"], "travel.walk")

    def test_grapevine(self):
        step = self._first("grapevine")
        self.assertEqual(step["symbol_id"], "travel.chasse")

    def test_sashay(self):
        step = self._first("sashay")
        self.assertEqual(step["symbol_id"], "travel.chasse")

    def test_tiptoe(self):
        step = self._first("tiptoe")
        self.assertEqual(step["symbol_id"], "travel.walk")


class BackwardCompatibilityTests(unittest.TestCase):
    """All original patterns continue to work exactly as before."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_step(self):
        self.assertEqual(self._first("step forward")["symbol_id"], "support.step")

    def test_walk(self):
        self.assertEqual(self._first("walk")["symbol_id"], "support.step")

    def test_turn(self):
        self.assertEqual(self._first("turn right")["symbol_id"], "turn.pivot")

    def test_pivot(self):
        self.assertEqual(self._first("pivot")["symbol_id"], "turn.pivot")

    def test_jump(self):
        self.assertEqual(self._first("jump")["symbol_id"], "jump.small")

    def test_leap(self):
        self.assertEqual(self._first("leap")["symbol_id"], "jump.small")

    def test_hop(self):
        self.assertEqual(self._first("hop")["symbol_id"], "jump.small")

    def test_glide(self):
        self.assertEqual(self._first("glide")["symbol_id"], "surface.glide")

    def test_brush(self):
        self.assertEqual(self._first("brush")["symbol_id"], "surface.brush")

    def test_reach(self):
        self.assertEqual(self._first("reach")["symbol_id"], "gesture.arm")

    def test_gesture(self):
        self.assertEqual(self._first("gesture")["symbol_id"], "gesture.arm")

    def test_rest(self):
        self.assertEqual(self._first("rest")["symbol_id"], "music.rest.quarter")

    def test_silence(self):
        self.assertEqual(self._first("silence")["symbol_id"], "music.rest.quarter")

    def test_tempo(self):
        self.assertEqual(self._first("tempo 120")["symbol_id"], "music.tempo.mark")

    def test_time_signatures(self):
        self.assertEqual(self._first("2/4")["symbol_id"], "music.time.2_4")
        self.assertEqual(self._first("3/4")["symbol_id"], "music.time.3_4")
        self.assertEqual(self._first("4/4")["symbol_id"], "music.time.4_4")


class SupportDetailsTests(unittest.TestCase):
    """Expanded support vocabulary."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_kneel(self):
        self.assertEqual(self._first("kneel")["symbol_id"], "support.kneel")

    def test_lunge(self):
        self.assertEqual(self._first("lunge")["symbol_id"], "support.lunge")

    def test_stamp(self):
        self.assertEqual(self._first("stamp")["symbol_id"], "support.stamp")

    def test_stomp(self):
        self.assertEqual(self._first("stomp")["symbol_id"], "support.stamp")

    def test_stand(self):
        self.assertEqual(self._first("stand")["symbol_id"], "support.stand")

    def test_weight_transfer(self):
        self.assertEqual(self._first("weight transfer")["symbol_id"], "support.transfer")

    def test_shift_weight(self):
        self.assertEqual(self._first("shift weight")["symbol_id"], "support.transfer")

    def test_lower(self):
        self.assertEqual(self._first("lower")["symbol_id"], "support.lower")

    def test_rise(self):
        self.assertEqual(self._first("rise")["symbol_id"], "support.rise")

    def test_on_toes(self):
        self.assertEqual(self._first("on toes")["symbol_id"], "support.toe")

    def test_on_heels(self):
        self.assertEqual(self._first("on heels")["symbol_id"], "support.heel")


class PathShapeTests(unittest.TestCase):
    """Path shape terms produce correct symbol_ids."""

    def _first(self, prompt: str) -> dict:
        plan = parse_phrase(prompt)
        self.assertGreaterEqual(len(plan["steps"]), 1, f"No steps for: {prompt!r}")
        return plan["steps"][0]

    def test_straight_path(self):
        self.assertEqual(self._first("straight path")["symbol_id"], "path.straight")

    def test_curved_path(self):
        self.assertEqual(self._first("curved path")["symbol_id"], "path.curved")

    def test_circular_path(self):
        self.assertEqual(self._first("circular path")["symbol_id"], "path.circle")

    def test_spiral_path(self):
        self.assertEqual(self._first("spiral path")["symbol_id"], "path.spiral")

    def test_circle(self):
        self.assertEqual(self._first("circle")["symbol_id"], "path.circle")


if __name__ == "__main__":
    unittest.main()
