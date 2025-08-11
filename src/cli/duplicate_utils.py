#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duplicate processing utilities decoupled from CLI frameworks and heavy deps.
Implements overlap grouping (exact/contain/overlap) and keep policies
(widest/first/last/entity-order) for plain and structured detections.
"""
from typing import Any, Dict, List, Optional, Tuple


def _components(n: int, edges: List[Tuple[int, int]]):
    g = [[] for _ in range(n)]
    for a, b in edges:
        g[a].append(b)
        g[b].append(a)
    seen = [False] * n
    comps = []
    from collections import deque

    for i in range(n):
        if seen[i]:
            continue
        q = deque([i])
        seen[i] = True
        cur = []
        while q:
            v = q.popleft()
            cur.append(v)
            for w in g[v]:
                if not seen[w]:
                    seen[w] = True
                    q.append(w)
        comps.append(cur)
    return comps


def _interval_len(d: Dict[str, Any]) -> int:
    return max(0, int(d.get("end", 0)) - int(d.get("start", 0)))


def _plain_edges(items: List[Dict[str, Any]], overlap: str):
    n = len(items)
    edges: List[Tuple[int, int]] = []
    if overlap == "exact":
        sig_map: Dict[Tuple[int, int], List[int]] = {}
        for i, d in enumerate(items):
            key = (int(d.get("start", -1)), int(d.get("end", -1)))
            sig_map.setdefault(key, []).append(i)
        for idxs in sig_map.values():
            if len(idxs) > 1:
                base = idxs[0]
                for j in idxs[1:]:
                    edges.append((base, j))
        return n, edges
    for i in range(n):
        si, ei = int(items[i].get("start", -1)), int(items[i].get("end", -1))
        for j in range(i + 1, n):
            sj, ej = int(items[j].get("start", -1)), int(items[j].get("end", -1))
            if overlap == "contain":
                dup = (si <= sj and ej <= ei) or (sj <= si and ei <= ej)
            else:  # overlap
                dup = (si <= ej) and (sj <= ei)
            if dup:
                edges.append((i, j))
    return n, edges


def _rect_area(q):
    x0, y0, x1, y1 = map(float, q)
    return max(0.0, (x1 - x0)) * max(0.0, (y1 - y0))


def _rect_intersects(a, b):
    ax0, ay0, ax1, ay1 = map(float, a)
    bx0, by0, bx1, by1 = map(float, b)
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    return (ix1 - ix0) > 0 and (iy1 - iy0) > 0


def _rect_contains(outer, inner, eps=0.01):
    ox0, oy0, ox1, oy1 = map(float, outer)
    ix0, iy0, ix1, iy1 = map(float, inner)
    return (
        ix0 >= ox0 - eps and iy0 >= oy0 - eps and ix1 <= ox1 + eps and iy1 <= oy1 + eps
    )


def _norm_quads(quads: List[List[float]]):
    rounded = [tuple(round(float(v), 2) for v in q) for q in (quads or [])]
    return tuple(sorted(rounded))


def _structured_edges(items: List[Dict[str, Any]], overlap: str):
    n = len(items)
    edges: List[Tuple[int, int]] = []
    by_page: Dict[int, List[int]] = {}
    for i, d in enumerate(items):
        by_page.setdefault(int(d.get("page", 0)), []).append(i)
    for page, idxs in by_page.items():
        if overlap == "exact":
            sig_map: Dict[Tuple, List[int]] = {}
            for i in idxs:
                sig = (page, _norm_quads(items[i].get("quads", [])))
                sig_map.setdefault(sig, []).append(i)
            for group in sig_map.values():
                if len(group) > 1:
                    base = group[0]
                    for j in group[1:]:
                        edges.append((base, j))
            continue
        m = len(idxs)
        for a in range(m):
            ia = idxs[a]
            qa = items[ia].get("quads", []) or []
            for b in range(a + 1, m):
                ib = idxs[b]
                qb = items[ib].get("quads", []) or []
                dup = False
                if overlap == "contain":
                    def a_in_b(A, B):
                        return all(any(_rect_contains(bq, aq) for bq in B) for aq in A)
                    dup = a_in_b(qa, qb) or a_in_b(qb, qa)
                else:
                    dup = any(_rect_intersects(aq, bq) for aq in qa for bq in qb)
                if dup:
                    edges.append((ia, ib))
    return n, edges


def _choose_kept(
    idxs: List[int],
    items: List[Dict[str, Any]],
    kind: str,
    keep: str,
    pri_map: Dict[str, int],
):
    if keep == "first":
        return idxs[0]
    if keep == "last":
        return idxs[-1]
    if keep == "entity-order":
        def prio(i):
            ent = str(items[i].get("entity", ""))
            return pri_map.get(ent, 10**9)

        return min(idxs, key=lambda i: (prio(i), idxs.index(i)))
    # widest
    if kind == "plain":
        return max(idxs, key=lambda i: (_interval_len(items[i]), -idxs.index(i)))
    else:
        def total_area(i):
            return sum(_rect_area(q) for q in (items[i].get("quads", []) or []))

        return max(idxs, key=lambda i: (total_area(i), -idxs.index(i)))


def dedupe_detections(
    detections: Dict[str, Any],
    overlap: str = "overlap",
    keep: str = "widest",
    entity_priority: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    plain = detections.get("plain", []) or []
    struct = detections.get("structured", []) or []
    pri_map = {name: i for i, name in enumerate(entity_priority or [])}

    n_p, e_p = _plain_edges(plain, overlap)
    comps_p = _components(n_p, e_p)
    kept_plain_idx = set(
        _choose_kept(c, plain, "plain", keep, pri_map) for c in comps_p if c
    )
    plain_out = [d for i, d in enumerate(plain) if i in kept_plain_idx]

    n_s, e_s = _structured_edges(struct, overlap)
    comps_s = _components(n_s, e_s)
    kept_struct_idx = set(
        _choose_kept(c, struct, "structured", keep, pri_map) for c in comps_s if c
    )
    struct_out = [d for i, d in enumerate(struct) if i in kept_struct_idx]

    return {"plain": plain_out, "structured": struct_out}

