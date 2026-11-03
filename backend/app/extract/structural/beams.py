"""Find every beam by following its drawn edge lines.

A beam is drawn as two parallel lines (straight, angled or curved) the beam's width
apart. The reader joins the short edge segments into chains, finds the partner line
at the schedule width, cuts the beam at real columns/walls (hanging columns only
trim the ends), splits lines shared by several labels at the support between them,
and trims T-junctions and corners. Ported from the method validated on the Nishika
Elysium 14th floor. All lengths in mm.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

from app.extract.structural.config import StructuralConfig
from app.extract.structural.entities import ColumnHatch, Prim, TextItem
from app.extract.structural.schedule import BeamSchedule

BEAM_TAG_RX = re.compile(r"^(B\d+[A-Z]?|BKT[\w-]*|HB)$")
SIZE_RX = re.compile(r"^\(?(\d{3})X(\d{3,4})(/\d{3})?\)?$")


@dataclass
class BeamResult:
    name: str
    width: int                      # mm, as used for the geometry
    depth: Optional[int]            # mm, from the schedule / plan label
    length_mm: int
    curved: bool
    edge: bool                      # matched against non-beam-coloured edge lines
    kind: str = ""                  # cantilever | inverted | sunken | ""
    size_source: str = "schedule"   # schedule | plan label | U.N.O. default
    flags: List[str] = field(default_factory=list)
    geom: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class _Cand:
    score: float
    A: LineString
    side: int
    w: float
    cen: LineString
    yellow: bool
    dist: float


def _angdiff(a: float, b: float) -> float:
    d = abs(a - b) % 180
    return min(d, 180 - d)


def _straight(g: LineString, tol: float = 20) -> bool:
    ch = LineString([g.coords[0], g.coords[-1]])
    return max(Point(c).distance(ch) for c in g.coords) < tol


def _local_dir(A: LineString, p: Point) -> float:
    s = A.project(p)
    q1 = A.interpolate(max(0, s - 150))
    q2 = A.interpolate(min(A.length, s + 150))
    return math.degrees(math.atan2(q2.y - q1.y, q2.x - q1.x)) % 180


def _chains(prims: Sequence[Prim], cfg: StructuralConfig) -> List[LineString]:
    """Join beam edge segments end to end (within node_tol, keeping direction)."""
    segs = [p.points() for p in prims
            if p.layer in cfg.beam_line_layers and p.aci in cfg.beam_line_aci
            and (p.kind == "arc" or math.dist(p.a, p.b) > 50)]
    nodes: List[Tuple[float, float]] = []

    def node_of(q: Tuple[float, float]) -> int:
        for i, n in enumerate(nodes):
            if math.dist(n, q) < cfg.node_tol:
                return i
        nodes.append(q)
        return len(nodes) - 1

    E: List[List] = []
    for s in segs:
        E.append([node_of(s[0]), node_of(s[-1]), s])
    adj: Dict[int, List[int]] = {}
    for k, (a, b, _s) in enumerate(E):
        adj.setdefault(a, []).append(k)
        adj.setdefault(b, []).append(k)

    def dirv(s: List[Tuple[float, float]], at_start: bool) -> Tuple[float, float]:
        p, q = (s[0], s[1]) if at_start else (s[-1], s[-2])
        d = math.dist(p, q) or 1
        return ((q[0] - p[0]) / d, (q[1] - p[1]) / d)

    used = set()
    chains: List[LineString] = []

    def extend(pts: List[Tuple[float, float]], node: int, last_dir: Tuple[float, float]):
        while True:
            best = None
            for k in adj.get(node, []):
                if k in used:
                    continue
                a, b, s = E[k]
                ss = s if a == node else s[::-1]
                d = dirv(ss, True)
                cosang = -(d[0] * last_dir[0] + d[1] * last_dir[1])
                if cosang > math.cos(math.radians(40)) and (best is None or cosang > best[0]):
                    best = (cosang, k, ss)
            if not best:
                return pts
            _, k, ss = best
            used.add(k)
            pts += ss[1:]
            node = E[k][1] if E[k][0] == node else E[k][0]
            last_dir = dirv(ss, False)

    for k, (a, b, s) in enumerate(E):
        if k in used:
            continue
        used.add(k)
        pts = extend(list(s), b, dirv(s, False))
        rev = extend(list(reversed(pts)), a, dirv(s, True))
        chains.append(LineString(rev))
    return chains


def find_beams(prims: Sequence[Prim], columns: Sequence[ColumnHatch], texts: Sequence[TextItem],
               schedule: BeamSchedule, cfg: StructuralConfig,
               ) -> Tuple[Dict[str, List[BeamResult]], Dict[str, str]]:
    WTOL = cfg.width_tol
    chains = _chains(prims, cfg)
    # edge lines: slab-layer lines and off-colour beam-layer lines can be the far side
    # of an edge beam (drawn once, shared with the slab outline)
    edge = [LineString(p.points()) for p in prims
            if not (p.layer in cfg.beam_line_layers and p.aci in cfg.beam_line_aci)]
    edge = [g for g in edge if g.length > 200]

    real, hang = [], []
    for c in columns:
        for pl in c.polys:
            try:
                pg = Polygon(pl).buffer(0)
                if pg.area < 1000:
                    continue
                (hang if c.kind == "hanging" else real).append(pg)
            except Exception:  # noqa: BLE001
                pass
    REAL = unary_union(real).buffer(5) if real else Polygon()
    HANG = unary_union(hang).buffer(5) if hang else Polygon()

    tags = [t for t in texts if t.layer in cfg.beam_tag_layers
            and BEAM_TAG_RX.match(t.text.replace(" ", "").upper())]
    plan_sizes = []
    for t in texts:
        if t.layer not in cfg.beam_size_layers:
            continue
        m = SIZE_RX.match(t.text.replace(" ", "").upper())
        if m:
            plan_sizes.append((t, (int(m.group(1)), int(m.group(2)))))

    def paired_plan_size(t: TextItem) -> Optional[Tuple[int, int]]:
        """The size label written along the same direction next to the name."""
        tv = 60 < (t.rot % 180) < 120
        best = None
        for z, s in plan_sizes:
            zv = 60 < (z.rot % 180) < 120
            if tv != zv:
                continue
            d = (abs(t.cx - z.cx) * 2 + abs(t.cy - z.cy)) if not tv else (abs(t.cy - z.cy) * 2 + abs(t.cx - z.cx))
            if d < 600 and (best is None or d < best[0]):
                best = (d, s)
        return best[1] if best else None

    def candidates(p: Point, th: float, W: float, strict: bool) -> List[_Cand]:
        out: List[_Cand] = []
        for A in chains:
            if A.distance(p) > 1600:
                continue
            if _angdiff(_local_dir(A, p), th) > 25:
                continue
            for side in (1, -1):
                for w in ([W] if strict else list(cfg.loose_widths)):
                    try:
                        off = A.offset_curve(side * w)
                    except Exception:  # noqa: BLE001
                        continue
                    if off.is_empty:
                        continue
                    band = off.buffer(WTOL if strict else 15)
                    sup_y = sum(c.intersection(band).length for c in chains if c is not A)
                    sup_e = sum(e.intersection(band).length for e in edge)
                    frac = max(sup_y, 0.7 * sup_e) / max(A.length, 1)
                    if frac < 0.3:
                        continue
                    cen = A.offset_curve(side * w / 2)
                    if cen.geom_type != "LineString":
                        cen = max(cen.geoms, key=lambda g: g.length)
                    out.append(_Cand(score=cen.distance(p) - 300 * min(frac, 1), A=A, side=side, w=w,
                                     cen=cen, yellow=sup_y >= 0.7 * sup_e, dist=cen.distance(p)))
        return out

    def build(c: _Cand, p: Point) -> LineString:
        cen = c.cen
        if cen.geom_type != "LineString":
            cen = max(cen.geoms, key=lambda g: g.length)
        if c.yellow and _straight(c.A):
            oc = c.A.offset_curve(c.side * c.w)
            band = oc.buffer(WTOL + 10)
            parts = [ch for ch in chains if ch is not c.A and ch.intersection(band).length > 100 and _straight(ch)]
            a0, a1 = c.A.coords[0], c.A.coords[-1]
            L = math.dist(a0, a1)
            ux, uy = (a1[0] - a0[0]) / L, (a1[1] - a0[1]) / L
            o = cen.coords[0]
            prj = [0, cen.length]
            for ch in parts:
                for q in (ch.coords[0], ch.coords[-1]):
                    prj.append((q[0] - o[0]) * ux + (q[1] - o[1]) * uy)
            lo, hi = min(prj), max(prj)
            cen = LineString([(o[0] + ux * lo, o[1] + uy * lo), (o[0] + ux * hi, o[1] + uy * hi)])
        return cen

    def pieces_of(cen: LineString, W: float) -> List[LineString]:
        g = cen.difference(REAL)
        parts = [x for x in getattr(g, "geoms", [g]) if x.length > 100]
        out = []
        for x in parts:  # hanging columns only trim the ends
            h = x.difference(HANG)
            hp = [y for y in getattr(h, "geoms", [h]) if y.length > 100]
            if len(hp) >= 2 and sorted(y.length for y in hp)[-2] > 600:
                out.append(x)
            else:
                out += hp or [x]
        final = []
        for x in out:   # cut where another beam crosses right through
            cuts = []
            for ch in chains:
                if ch.distance(x) > 1:
                    continue
                inter = ch.intersection(x)
                if inter.is_empty or inter.geom_type not in ("Point", "MultiPoint"):
                    continue
                a, b = Point(ch.coords[0]), Point(ch.coords[-1])
                pt0 = list(getattr(inter, "geoms", [inter]))[0]
                if a.distance(x) > W / 2 + 150 and b.distance(x) > W / 2 + 150 \
                        and _angdiff(_local_dir(ch, pt0), _local_dir(x, pt0)) > 45:
                    for q in getattr(inter, "geoms", [inter]):
                        cuts.append(x.project(q))
            if cuts:
                cuts = sorted(set(round(c) for c in cuts))
                prev = 0.0
                segs_ = []
                for c_ in cuts + [x.length]:
                    if c_ - prev > 100:
                        segs_.append(substring(x, prev, c_))
                    prev = c_
                final += [s for s in segs_ if s.length > 320] or segs_
            else:
                final.append(x)
        return final or [cen]

    results: Dict[str, List[dict]] = {}
    fails: Dict[str, str] = {}
    for t in tags:
        name = t.text.replace(" ", "").upper()
        row = schedule.by_name.get(name)
        plan = paired_plan_size(t)
        W: Optional[int] = row.B if row else (plan[0] if plan else None)
        size_source = "schedule" if row else ("plan label" if plan else "U.N.O. default")
        preflags: List[str] = []
        if row and plan and (plan[0] != row.B or plan[1] != row.D):
            preflags.append(f"plan label {plan[0]}x{plan[1]} but schedule says {row.B}x{row.D}")
        if W is None:
            W = cfg.default_beam_size[0]
            preflags.append(f"no size on plan or schedule: U.N.O. {cfg.default_beam_size[0]}x{cfg.default_beam_size[1]} applied")
        p = Point(t.cx, t.cy)
        th = t.rot % 180
        C = candidates(p, th, W, True)
        Cl = candidates(p, th, W, False)
        best = min(C, key=lambda c: c.score) if C else None
        loose = min(Cl, key=lambda c: c.score) if Cl else None
        flag = None
        if loose and (best is None or (best.dist > 900 and loose.dist < 0.5 * best.dist)):
            if best is None or loose.w != W:
                best = loose
                flag = f"drawn width {int(loose.w)} but schedule says {W}"
        if not best:
            fails[name] = "no line pair found near the label"
            continue
        cen = build(best, p)
        pcs = pieces_of(cen, W)
        piece = min(pcs, key=lambda g: g.distance(p))
        results.setdefault(name, []).append(dict(
            name=name, W=W, D=(row.D if row else (plan[1] if plan else cfg.default_beam_size[1])),
            kind=row.kind if row else "", size_source=size_source,
            piece=piece, p=p, t=t, yellow=best.yellow,
            flags=preflags + ([flag] if flag else [])))

    allr = [r for v in results.values() for r in v]

    def rematch(r: dict) -> bool:
        t, W, p = r["t"], r["W"], r["p"]
        th = t.rot % 180
        taken = [q["piece"] for q in allr if q is not r]
        C = candidates(p, th, W, True) + candidates(p, th, W, False)
        C = [c for c in C if not any(build(c, p).distance(tp) < 10 and abs(build(c, p).length - tp.length) < 2000
                                     for tp in taken)]
        if not C:
            return False
        c = min(C, key=lambda c: c.dist)
        cen = build(c, p)
        r["piece"] = min(pieces_of(cen, W), key=lambda g: g.distance(p))
        r["yellow"] = c.yellow
        if c.w != W:
            r["flags"] = [f for f in r["flags"] if "drawn width" not in f] + \
                         [f"drawn width {int(c.w)} but schedule says {W}"]
        return True

    # side-by-side labels fighting for one piece: the farther label moves on
    for r in allr:
        for q in allr:
            if q is r or q["name"] == r["name"] or not q["piece"].equals_exact(r["piece"], 1):
                continue
            pr, pq = r["piece"].project(r["p"]), q["piece"].project(q["p"])
            if abs(pr - pq) < 1500:
                worse = r if r["piece"].distance(r["p"]) > q["piece"].distance(q["p"]) else q
                rematch(worse)

    # several names on one piece: split at the support between them, else midpoint
    allr = [r for v in results.values() for r in v]
    for r in allr:
        if not r["name"].startswith("B") or r["name"].startswith("BKT"):
            continue
        same = [q for q in allr if q is not r and q["name"] != r["name"]
                and q["name"].startswith("B") and not q["name"].startswith("BKT")
                and q["piece"].equals_exact(r["piece"], 1)]
        if not same:
            continue
        grp = sorted([r] + same, key=lambda q: r["piece"].project(q["p"]))
        if r is not grp[0] and any(q.get("done") for q in grp):
            continue
        x = r["piece"]
        pos = [x.project(q["p"]) for q in grp]
        cutsat = []
        supports = REAL.union(HANG)
        for k in range(len(grp) - 1):
            lo, hi = pos[k], pos[k + 1]
            cand = []
            near = supports.intersection(x.buffer(grp[0]["W"] / 2 + 400))
            for geom in list(getattr(near, "geoms", [near])):
                if geom.is_empty or geom.area < 100:
                    continue
                pr = x.project(geom.centroid)
                if lo < pr < hi:
                    cand.append((abs(pr - (lo + hi) / 2), pr, geom))
            if cand:
                _, pr, geom = min(cand)
                cutsat.append((pr, geom))
            else:   # geometry change (curve start) between the labels, else midpoint
                best_at = None
                cs = list(x.coords)
                acc = 0.0
                prev_d = None
                for j in range(1, len(cs)):
                    d = math.degrees(math.atan2(cs[j][1] - cs[j - 1][1], cs[j][0] - cs[j - 1][0]))
                    if prev_d is not None and _angdiff(d, prev_d) > 8 and lo < acc < hi:
                        if best_at is None or abs(acc - (lo + hi) / 2) < abs(best_at - (lo + hi) / 2):
                            best_at = acc
                    acc += math.dist(cs[j], cs[j - 1])
                    prev_d = d
                cutsat.append((best_at if best_at is not None else (lo + hi) / 2, None))
        bounds = [0] + [c for c, _ in cutsat] + [x.length]
        for k, q in enumerate(grp):
            a_, b_ = bounds[k], bounds[k + 1]
            sub = substring(x, a_, b_)
            geom = cutsat[k - 1][1] if k > 0 else None
            if geom is not None:
                pa = [x.project(Point(c)) for c in geom.exterior.coords]
                sub = substring(x, max(a_, max(pa)), b_)
            geom2 = cutsat[k][1] if k < len(cutsat) else None
            if geom2 is not None:
                pa2 = [x.project(Point(c)) for c in geom2.exterior.coords]
                lo_ = a_ if geom is None else max(a_, max(x.project(Point(c)) for c in geom.exterior.coords))
                sub = substring(x, lo_, min(b_, min(pa2)))
            if sub.length < 100:
                sub = substring(x, a_, b_)
            q["piece"] = sub
            q["done"] = True

    # T-junctions and corners: trim the longer member where another beam runs past
    final = [r for v in results.values() for r in v]
    for r in final:
        x = r["piece"]
        if x.length < 200:
            continue
        a, b = 0.0, x.length
        for q in final:
            if q is r:
                continue
            y = q["piece"]
            if y.length < 300 or _angdiff(_local_dir(y, y.interpolate(y.length / 2)),
                                          _local_dir(x, x.interpolate(x.length / 2))) < 45:
                continue
            band = y.buffer(q["W"] / 2)
            for end in ("a", "b"):
                E = Point(x.coords[0]) if end == "a" else Point(x.coords[-1])
                if band.contains(E):
                    s0 = y.project(E)
                    through = s0 > q["W"] / 2 + 100 and y.length - s0 > q["W"] / 2 + 100
                    # a member whose own match is flagged (no size anywhere, or drawn
                    # width off) is too uncertain to trim another beam's corner
                    corner_and_longer = (not through) and x.length > y.length and not q["flags"]
                    if through or corner_and_longer:
                        inside = x.intersection(band).length
                        if end == "a":
                            a = max(a, inside)
                        else:
                            b = min(b, x.length - inside)
        if (a > 0 or b < x.length) and b - a >= 0.5 * x.length and b - a > cfg.min_beam_len:
            r["piece"] = substring(x, a, b)

    out: Dict[str, List[BeamResult]] = {}
    for nm, v in results.items():
        out[nm] = [BeamResult(name=nm, width=int(r["W"]), depth=r["D"], length_mm=round(r["piece"].length),
                              curved=not _straight(r["piece"]), edge=not r["yellow"], kind=r["kind"],
                              size_source=r["size_source"], flags=list(r["flags"]),
                              geom=list(r["piece"].coords)) for r in v]
    return out, fails
