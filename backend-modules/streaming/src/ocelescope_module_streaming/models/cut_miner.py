"""Discovery of process trees from DF2 graphs (definitions.tex: def:ocpt).

`DF2InductiveMiner` ports `find_cuts_start` of the Rust reference
(BPM-Research-Group/scope, `backend/src/core/df2_miner/start_cuts_opti.rs`), including its
iteration orders, so that both produce the same trees. The only intended difference: where no
cut applies, the Rust code returns its activities as separate trees, which a parent operator
absorbs as extra children; here they form an explicit `no_cut` node.
"""

from collections import deque
from collections.abc import Iterable
from typing import Protocol

from ocelescope_module_streaming.models.process_tree import NodeKind, ProcessTreeNode

Edge = tuple[str, str]


class CutMiner(Protocol):
    """Turns a DF2 graph into a process tree of unannotated activity leaves."""

    def mine(
        self, edges: Iterable[Edge], activities: Iterable[str], starts: Iterable[str], ends: Iterable[str]
    ) -> ProcessTreeNode: ...


class DF2InductiveMiner:
    """Inductive-miner-style cut detection: xor, then sequence, parallel and loop."""

    def mine(
        self, edges: Iterable[Edge], activities: Iterable[str], starts: Iterable[str], ends: Iterable[str]
    ) -> ProcessTreeNode:
        return _find_cuts(frozenset(edges), frozenset(activities), frozenset(starts), frozenset(ends))


def _leaf(activity: str) -> ProcessTreeNode:
    return ProcessTreeNode(kind="activity", activity=activity)


def _find_cuts(
    dfg: frozenset[Edge], activities: frozenset[str], starts: frozenset[str], ends: frozenset[str]
) -> ProcessTreeNode:
    ordered = sorted(activities)
    if len(ordered) == 1:
        return _leaf(ordered[0])

    filtered = frozenset((a, b) for a, b in dfg if a in activities and b in activities)
    starts, ends = _start_and_end_activities(dfg, activities, starts, ends)

    def node(kind: NodeKind, first: frozenset[str], second: frozenset[str]) -> ProcessTreeNode:
        children = [_find_cuts(dfg, part, starts, ends) for part in (first, second)]
        return ProcessTreeNode(kind=kind, children=children)

    first, second = _exclusive_choice_cut(filtered, activities)
    if first and second and not any((a, b) in filtered or (b, a) in filtered for a in first for b in second):
        return node("xor", first, second)

    first, second = _sequence_cut(filtered, activities)
    if first and second and _is_sequence_cut_possible(filtered, first, second):
        return node("sequence", first, second)

    possible, first, second = _parallel_cut(filtered, activities)
    if possible and first and second and all(part & starts and part & ends for part in (first, second)):
        return node("parallel", first, second)

    possible, first, second = _redo_cut(filtered, activities, starts, ends)
    if possible and first and second and _redo_condition(filtered, first, second, starts, ends):
        return node("loop", first, second)

    return ProcessTreeNode(kind="no_cut", children=[_leaf(activity) for activity in ordered])


# Exclusive choice: connected components of the undirected graph.


def _exclusive_choice_cut(dfg: frozenset[Edge], activities: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    neighbors: dict[str, set[str]] = {activity: set() for activity in activities}
    for a, b in dfg:
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)
    visited: set[str] = set()
    components: list[frozenset[str]] = []
    for activity in sorted(activities):
        if activity in visited:
            continue
        component: set[str] = set()
        queue = deque([activity])
        visited.add(activity)
        while queue:
            current = queue.popleft()
            component.add(current)
            for neighbor in sorted(neighbors.get(current, ())):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(frozenset(component))
    components.sort(key=min)
    if not components:
        return frozenset(), frozenset()
    return components[0], frozenset().union(*components[1:])


# Sequence: strongly connected components and their condensation.


def _sequence_cut(dfg: frozenset[Edge], activities: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    sccs = _strongly_connected_components(dfg, activities)
    component = {activity: index for index, scc in enumerate(sccs) for activity in scc}
    dag: dict[int, set[int]] = {}
    for a, b in dfg:
        if component[a] != component[b]:
            dag.setdefault(component[a], set()).add(component[b])

    first = {source for source, targets in dag.items() if targets}
    second = {target for targets in dag.values() for target in targets}
    common = first & second
    first -= common
    second -= common
    for c in sorted(common):
        if all(_dag_reachable(dag, t, c) and not _dag_reachable(dag, c, t) for t in sorted(first)):
            second.add(c)
        else:
            first.add(c)
    return (
        frozenset(activity for index in first for activity in sccs[index]),
        frozenset(activity for index in second for activity in sccs[index]),
    )


def _strongly_connected_components(dfg: frozenset[Edge], activities: frozenset[str]) -> list[list[str]]:
    """Tarjan's algorithm, iteratively; SCCs are sorted, and ordered by their first activity."""
    graph: dict[str, list[str]] = {activity: [] for activity in activities}
    for a, b in dfg:
        graph.setdefault(a, []).append(b)
    for targets in graph.values():
        targets.sort()

    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []
    counter = 0
    for root in sorted(activities):
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, child = work.pop()
            if child == 0:
                index[node] = lowlink[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            recurse = False
            targets = graph.get(node, [])
            while child < len(targets):
                target = targets[child]
                child += 1
                if target not in index:
                    work.append((node, child))
                    work.append((target, 0))
                    recurse = True
                    break
                if target in on_stack:
                    lowlink[node] = min(lowlink[node], index[target])
            if recurse:
                continue
            if lowlink[node] == index[node]:
                scc: list[str] = []
                while True:
                    top = stack.pop()
                    on_stack.discard(top)
                    scc.append(top)
                    if top == node:
                        break
                sccs.append(sorted(scc))
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    sccs.sort(key=lambda scc: scc[0])
    return sccs


def _dag_reachable(dag: dict[int, set[int]], source: int, target: int) -> bool:
    visited: set[int] = set()
    stack = [source]
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current not in visited:
            visited.add(current)
            stack.extend(dag.get(current, ()))
    return False


def _reachable(dfg: frozenset[Edge], source: str, target: str) -> bool:
    visited: set[str] = set()
    stack = [source]
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current not in visited:
            visited.add(current)
            stack.extend(b for a, b in dfg if a == current)
    return False


def _is_sequence_cut_possible(dfg: frozenset[Edge], first: frozenset[str], second: frozenset[str]) -> bool:
    return all(_reachable(dfg, a, b) for a in first for b in second) and not any(
        _reachable(dfg, b, a) for b in second for a in first
    )


# Parallel: every activity of one part is connected both ways with every activity of the other.


def _both_ways(dfg: frozenset[Edge], first: Iterable[str], second: Iterable[str]) -> bool:
    second = list(second)
    return all((m, n) in dfg and (n, m) in dfg for m in first for n in second)


def _parallel_cut(dfg: frozenset[Edge], activities: frozenset[str]) -> tuple[bool, frozenset[str], frozenset[str]]:
    first: set[str] = set()
    second: set[str] = set()
    for activity in sorted(activities):
        if not first:
            first.add(activity)
            continue
        if _both_ways(dfg, [activity], first):
            second.add(activity)
        elif not second:
            first.add(activity)
        elif _both_ways(dfg, [activity], second):
            first.add(activity)
        else:
            return False, frozenset(first), frozenset(second)
    return True, frozenset(first), frozenset(second)


# Loop (redo): the body holds start and end activities, the redo part leads back to the start.


def _redo_cut(
    dfg: frozenset[Edge], activities: frozenset[str], starts: frozenset[str], ends: frozenset[str]
) -> tuple[bool, frozenset[str], frozenset[str]]:
    body = set(starts | ends)
    redo: set[str] = set()
    for x in sorted(activities):
        if x in body:
            continue
        in_body = _reachable_before(dfg, starts, x, ends)
        in_redo = _reachable_before(dfg, ends, x, starts)
        if in_body and not in_redo:
            body.add(x)
        elif in_redo and not in_body:
            redo.add(x)
        else:
            return False, frozenset(body), frozenset(redo)
    return True, frozenset(body), frozenset(redo)


def _reachable_before(dfg: frozenset[Edge], sources: frozenset[str], target: str, blocked: frozenset[str]) -> bool:
    """Whether `target` is reachable from a source without passing through `blocked`."""
    for source in sorted(sources):
        visited: set[str] = set()
        stack = [source]
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current in visited or current in blocked:
                continue
            visited.add(current)
            stack.extend(b for a, b in dfg if a == current)
    return False


def _redo_condition(
    dfg: frozenset[Edge], body: frozenset[str], redo: frozenset[str], starts: frozenset[str], ends: frozenset[str]
) -> bool:
    return (
        starts <= body
        and ends <= body
        and any((e, x) in dfg for e in ends for x in redo)
        and any((x, s) in dfg for x in redo for s in starts)
        and all(any((e, b) in dfg for b in redo) for e in ends)
        and all(any((b, s) in dfg for b in redo) for s in starts)
    )


def _start_and_end_activities(
    dfg: frozenset[Edge], activities: frozenset[str], starts: frozenset[str], ends: frozenset[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """Start and end activities of a part: entered or left from outside, or globally so."""
    local_starts = {b for a, b in dfg if a not in activities and b in activities} | (starts & activities)
    local_ends = {a for a, b in dfg if a in activities and b not in activities} | (ends & activities)
    return frozenset(local_starts), frozenset(local_ends)
