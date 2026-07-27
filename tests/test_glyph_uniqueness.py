"""Guards the parity metric: how many *distinct glyphs* the catalog produces.

Catalog size and rendering capability drifted 7:1 apart before this existed —
adding a catalog entry raised the symbol count while the renderer's graphic
vocabulary stood still, so "1122 symbols" read as parity progress when it was
padding. Only the second number is parity.

Method: render every catalog symbol in isolation into the same slot, strip the
id, and group by the remaining markup. Symbols in one group engrave
identically. Coordinates are kept — they carry shape.

Not every collision is a defect. In Labanotation a direction symbol encodes
direction and level only, so `support.balance.backward` and
`support.heel.backward` genuinely share a glyph — heel support and balance ride
on pre-signs attached to it. Those clusters are expected; see
EXPECTED_SHARED_GLYPH_FAMILIES.
"""
import collections
import hashlib
import re
import unittest

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.rendering.laban_renderer import render_laban_svg

# Measured floors, not aspirations. Raise them when the renderer improves;
# never lower one to make a change pass.
MIN_DISTINCT_GLYPHS = 474
MAX_CLUSTER_SIZE = 33

# Families whose members legitimately share a glyph.
#
# support/gesture/travel: a direction symbol encodes direction and level only.
#   Heel support, balance, kneel and the rest are carried by pre-signs attached
#   beside it, so those actions share the direction symbol by design. (Plié and
#   relevé are a different case — they ARE a level, see the audit doc.)
#
# direction: direction.place IS a place direction symbol, so it sharing with
#   gesture.arm.place.middle is the notation working, not a defect.
#
# flexion/extension: the mark for a 45-degree flexion is the same mark whatever
#   joint it applies to; the joint is carried by which limb the mark attaches
#   to, and the probe deliberately renders everything into one slot.
EXPECTED_SHARED_GLYPH_FAMILIES = {"support", "gesture", "travel", "direction",
                                  "flexion", "extension"}

# Families with a KNOWN, UNFIXED collapse: the id names a variant the renderer
# discards, and the catalog gives that variant its own glyph. These are a work
# list, not an exemption — the assertion below requires the set to shrink and
# fails if a family is added to it without being listed here first.
#
KNOWN_OPEN_COLLAPSES: set[str] = set()

_GROUP = re.compile(r"<(/?)g\b[^>]*?(/?)>")


def _symbol_markup(svg: str, symbol_id: str) -> str | None:
    """The balanced <g> element carrying this symbol's id."""
    i = svg.find(f'data-symbol-id="{symbol_id}"')
    if i == -1:
        return None
    start = svg.rfind("<g", 0, i)
    depth = 0
    for m in _GROUP.finditer(svg, start):
        if m.group(2) == "/":
            continue                      # self-closing <g/>
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return svg[start:m.end()]
    return None


def _fingerprint(markup: str) -> str:
    """Hash of the drawing alone, with only the id removed.

    Coordinates are deliberately kept. They carry shape: an arrow pointing up
    and one pointing down differ in nothing else, and a zone marker says which
    zone by where it puts the filled cell. Blanking x/y made those collide.

    Comparing raw coordinates is only sound because every symbol is rendered
    into the same slot — see PROBE_BODY_PART.
    """
    return hashlib.md5(
        re.sub(r'data-symbol-id="[^"]*"', "", markup).encode()).hexdigest()[:12]


# One body part for every symbol, so column placement is constant and raw
# coordinates are comparable between symbols. Using each symbol's own first
# allowed body part would put them in different columns and make symbols that
# draw the same glyph look distinct.
PROBE_BODY_PART = "torso"


def _render_whole_catalog() -> tuple[dict[str, list[str]], list[str]]:
    """{fingerprint: [symbol_id, ...]}, plus ids that drew nothing."""
    catalog = load_symbol_catalog()
    groups: dict[str, list[str]] = collections.defaultdict(list)
    undrawn: list[str] = []
    for symbol_id, spec in sorted(catalog.items()):
        ir = {
            "schema_version": "1.0",
            "metadata": {"title": "probe",
                         "time_signature": {"numerator": 4, "denominator": 4}},
            "symbols": [{
                "symbol_id": symbol_id,
                "body_part": PROBE_BODY_PART,
                "timing": {"measure": 1, "beat": 1.0, "duration_beats": 1.0},
            }],
        }
        markup = _symbol_markup(render_laban_svg(ir), symbol_id)
        if markup is None:
            undrawn.append(symbol_id)
        else:
            groups[_fingerprint(markup)].append(symbol_id)
    return groups, undrawn


class GlyphUniquenessTests(unittest.TestCase):
    """Rendered once for the whole class — it draws every catalog symbol."""

    @classmethod
    def setUpClass(cls):
        cls.groups, cls.undrawn = _render_whole_catalog()
        cls.catalog_size = sum(len(v) for v in cls.groups.values()) + len(cls.undrawn)

    def test_every_catalog_symbol_draws_something(self):
        self.assertEqual(self.undrawn, [],
                         f"{len(self.undrawn)} symbols render to nothing")

    def test_distinct_glyph_count_does_not_regress(self):
        distinct = len(self.groups)
        self.assertGreaterEqual(
            distinct, MIN_DISTINCT_GLYPHS,
            f"{self.catalog_size} symbols now produce only {distinct} distinct "
            f"glyphs (floor {MIN_DISTINCT_GLYPHS}). Something stopped reading "
            f"information it used to read.",
        )

    def test_no_cluster_grows_beyond_the_recorded_maximum(self):
        largest = max(self.groups.values(), key=len)
        self.assertLessEqual(
            len(largest), MAX_CLUSTER_SIZE,
            f"{len(largest)} symbols now share one glyph (max {MAX_CLUSTER_SIZE}): "
            f"{largest[:6]}",
        )

    def test_large_clusters_only_contain_families_that_share_by_design(self):
        """A big cluster from any other family means information is being lost.

        This is the assertion that would have caught every defect found so far:
        contact ids collapsing on a mis-parsed segment, floor-plan sub-families
        reading a field they do not carry, flexion marks engraved as direction
        symbols.
        """
        for symbol_ids in self.groups.values():
            if len(symbol_ids) < 10:
                continue
            families = {s.split(".")[0] for s in symbol_ids}
            unexpected = families - EXPECTED_SHARED_GLYPH_FAMILIES
            unexpected -= KNOWN_OPEN_COLLAPSES
            self.assertEqual(
                unexpected, set(),
                f"{len(symbol_ids)} symbols share one glyph including "
                f"{sorted(unexpected)}, which do not share by design: "
                f"{symbol_ids[:6]}",
            )

    def test_the_known_open_collapse_list_only_shrinks(self):
        """Every family on the work list must still actually be collapsing.

        If one is fixed, this fails and the entry has to be deleted — which
        stops the list from quietly becoming a permanent exemption.
        """
        still_collapsing = {
            family
            for symbol_ids in self.groups.values() if len(symbol_ids) >= 4
            for family in {s.split(".")[0] for s in symbol_ids}
        } & KNOWN_OPEN_COLLAPSES
        fixed = KNOWN_OPEN_COLLAPSES - still_collapsing
        self.assertEqual(
            fixed, set(),
            f"{sorted(fixed)} no longer collapse — remove them from "
            f"KNOWN_OPEN_COLLAPSES.",
        )


if __name__ == "__main__":
    unittest.main()
