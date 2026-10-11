"""The BBS engine must reproduce the numbers in Avighna's own measurement sheet
('Measurement Sheet_14th Floor Reinforcement.xlsx'): beam B1A stirrups/SFR and slab S3 rows."""
from app.engine.bbs import compute_bbs, compute_member
from app.engine.boq import compute_boq, item_ref, round_qty
from app.models.schemas import (
    BarGroup, BeamSpec, ColumnSpec, ColumnTie, FitoutItem, SlabLayer, SlabSpec, StairFlight, StairSpec,
    Standards, StirrupZone, WallSpec,
)

STD = Standards()


def _rows(res):
    return {r.description: r for r in res.rows}


def test_beam_b1a_matches_reference_sheet():
    b = BeamSpec(tag="B1A", span_m=2.45, width_m=0.23, depth_m=0.75,
                 bottom_bars=[BarGroup(count=2, dia_mm=20)], top_bars=[BarGroup(count=2, dia_mm=20)],
                 stirrups=[StirrupZone(dia_mm=8, spacing_mm=100, zone="end"), StirrupZone(dia_mm=8, spacing_mm=150, zone="mid")],
                 sfr_bars=[BarGroup(count=2, dia_mm=8)])
    res = compute_member(b, STD)
    rows = list(res.rows)
    stir_end = next(r for r in rows if "@100" in r.description)
    stir_mid = next(r for r in rows if "@150" in r.description)
    sfr = next(r for r in rows if r.description.startswith("SFR"))
    # reference: 18 stirrups @100 (sides), 4 @150 (mid), cut 1.856 m, weights 13.196 / 2.932 kg; SFR 3.871 kg
    assert stir_end.bars_per_member == 18 and stir_mid.bars_per_member == 4
    assert abs(stir_end.cut_length_m - 1.856) < 1e-6
    assert abs(stir_end.weight_kg - 13.196) < 0.001 and abs(stir_mid.weight_kg - 2.932) < 0.001
    assert abs(sfr.weight_kg - 3.871) < 0.001
    main = next(r for r in rows if r.description.startswith("Main Bar Bottom"))
    # reference writes a=0.98, b=2.45, c=0.98 (gross 4.41); engine deducts the two 90-degree bends like row B1B does
    assert (main.a, main.b, main.c) == (0.98, 2.45, 0.98)
    assert abs(main.cut_length_m - (4.41 - 2 * 0.6 * 20 / 1000)) < 1e-6


def test_slab_s3_matches_reference_sheet():
    s = SlabSpec(tag="S3 near C6", length_m=4.9, width_m=5.35, thickness_m=0.175,
                 short_main=SlabLayer(dia_mm=8, spacing_mm=150, bent_up=True),
                 long_main=SlabLayer(dia_mm=8, spacing_mm=175, bent_up=True),
                 short_top_dist_end=SlabLayer(dia_mm=8, spacing_mm=150),
                 long_top_dist_end=SlabLayer(dia_mm=8, spacing_mm=175))
    res = compute_member(s, STD)
    r = list(res.rows)
    assert [x.bars_per_member for x in r] == [36, 29, 12, 10]
    assert [round(x.cut_length_m, 4) for x in r] == [5.3567, 5.8067, 5.3, 5.75]
    assert [round(x.weight_kg, 3) for x in r] == [76.172, 66.516, 25.122, 22.713]


def test_full_bbs_summary_tons():
    members = [
        BeamSpec(tag="B1", span_m=4.0, width_m=0.23, depth_m=0.45, bottom_bars=[BarGroup(count=3, dia_mm=16)],
                 top_bars=[BarGroup(count=2, dia_mm=12)], stirrups=[StirrupZone(dia_mm=8, spacing_mm=150)]),
        ColumnSpec(tag="C1", length_m=0.3, width_m=0.6, height_m=3.0, vertical_bars=[BarGroup(count=8, dia_mm=16)],
                   ties=[ColumnTie(dia_mm=8, spacing_mm=100)]),
        WallSpec(tag="W1", length_m=3.0, thickness_m=0.15, height_m=3.0, vertical=SlabLayer(dia_mm=8, spacing_mm=150),
                 horizontal=SlabLayer(dia_mm=8, spacing_mm=200)),
        StairSpec(tag="ST1", flights=[StairFlight(name="F1", width_m=1.575, waist_m=0.175, going_m=2.4, rise_m=1.5,
                                                  landing_a_m=1.2, main=SlabLayer(dia_mm=12, spacing_mm=100),
                                                  dist=SlabLayer(dia_mm=8, spacing_mm=150))]),
    ]
    res = compute_bbs(members, STD, "14th Floor")
    assert len(res.members) == 4
    assert [c.category for c in res.summary.categories] == ["Beam", "Column", "NSW / Wall", "Staircase"]
    assert abs(sum(res.summary.total_by_dia_t.values()) - res.summary.grand_total_t) < 1e-6
    assert res.summary.grand_total_t > 0.05


def test_boq_engine_rounding_and_refs():
    assert item_ref(0) == "A" and item_ref(25) == "Z" and item_ref(26) == "AA"
    assert round_qty(269.44, "m2") == 269.5 and round_qty(2.2, "nos") == 3 and round_qty(0, "lm") == 0
    items = [FitoutItem(division="finishes", section="Floor Finishes", code="FC-201", description="Stone", unit="m2", qty=270, rate=350),
             FitoutItem(division="lighting", section="Lighting", code="LI-501", description="Pendant", unit="nos", qty=3)]
    r = compute_boq(items, [], "AED")
    assert r.summary.subtotal == 94500 and r.summary.vat == 4725 and r.summary.grand_total == 99225
    assert r.summary.qty_by_unit == {"m2": 270.0, "nos": 3.0}
    assert r.sections[0].lines[0].amount == 94500 and r.sections[1].lines[0].amount is None
