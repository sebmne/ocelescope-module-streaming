"""Replays an Ocelescope OCEL as a stream.

Order: by timestamp; at equal timestamps events, then attribute updates, then O2O updates;
within a kind by id. O2O relations have no timestamp in an OCEL: each is placed at the first
event of its source object (as in Liss et al.). An object change without a field sets every
attribute it has a value for.
"""

import heapq
from collections.abc import Collection, Iterator
from contextlib import closing
from itertools import groupby
from typing import Any

from ocelescope import OCEL
from ocelescope.ocel.constants.pm4py import (
    ACTIVITY_COL,
    E2O_QUALIFIER,
    EID_COL,
    O2O_QUALIFIER,
    O2O_SOURCE_ID,
    O2O_TARGET_ID,
    OBJECT_CHANGED_FIELD,
    OID_COL,
    OTYPE_COL,
    TIMESTAMP_COL,
)
from ocelescope.ocel.constants.tables import E2O_TABLE, EVENTS_TABLE, O2O_TABLE, OBJECT_CHANGES_TABLE, OBJECTS_TABLE
from ocelescope.util.sql import ident

from ocelescope_module_streaming.stream.items import (
    AttributeUpdate,
    Event,
    ItemKind,
    O2OUpdate,
    ObjectRef,
    Relation,
    StreamItem,
)

BATCH_SIZE = 10_000
ALL_KINDS: tuple[ItemKind, ...] = (Event, AttributeUpdate, O2OUpdate)  # also the order at equal timestamps

_EID, _OID, _OTYPE, _TIME = ident(EID_COL), ident(OID_COL), ident(OTYPE_COL), ident(TIMESTAMP_COL)
_FIRST_SEEN = (  # each object's first event time
    f"SELECT r.{_OID} AS oid, min(e.{_TIME}) AS time "
    f"FROM {ident(E2O_TABLE)} r JOIN {ident(EVENTS_TABLE)} e ON e.{_EID} = r.{_EID} GROUP BY r.{_OID}"
)


def replay(ocel: OCEL, kinds: Collection[ItemKind] = ALL_KINDS) -> Iterator[StreamItem]:
    """Yields the items of the given kinds, merged in replay order and read in batches."""
    sources = {Event: _events, AttributeUpdate: _attribute_updates, O2OUpdate: _o2o_updates}
    streams = [sources[kind](ocel, rank) for rank, kind in enumerate(ALL_KINDS) if kind in kinds]
    # Keys (time, rank, index) are unique, so items themselves are never compared.
    return (item for _, item in heapq.merge(*streams))


def count_items(ocel: OCEL, kinds: Collection[ItemKind] = ALL_KINDS) -> int:
    """The number of items `replay` yields (field-less object changes count once)."""
    queries = {
        Event: f"SELECT count(DISTINCT r.{_EID}) FROM {ident(E2O_TABLE)} r "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = r.{_OID}",
        AttributeUpdate: f"SELECT count(*) FROM {ident(OBJECT_CHANGES_TABLE)} c "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = c.{_OID}",
        O2OUpdate: f"SELECT count(*) FROM {ident(O2O_TABLE)} x "
        f"JOIN ({_FIRST_SEEN}) f ON f.oid = x.{ident(O2O_SOURCE_ID)} "
        f"JOIN {ident(OBJECTS_TABLE)} s ON s.{_OID} = x.{ident(O2O_SOURCE_ID)} "
        f"JOIN {ident(OBJECTS_TABLE)} t ON t.{_OID} = x.{ident(O2O_TARGET_ID)}",
    }
    return sum(int(ocel.sql(queries[kind]).fetchall()[0][0]) for kind in kinds)


def _attribute_columns(ocel: OCEL, table: str, core: set[str]) -> list[str]:
    return [str(row[0]) for row in ocel.sql(f"DESCRIBE {ident(table)}").fetchall() if row[0] not in core]


def _rows(ocel: OCEL, query: str) -> Iterator[tuple[Any, ...]]:
    with closing(ocel.con.cursor()) as cursor:
        cursor.execute(query)
        while batch := cursor.fetchmany(BATCH_SIZE):
            yield from batch


def _events(ocel: OCEL, rank: int) -> Iterator[tuple[Any, StreamItem]]:
    columns = _attribute_columns(ocel, EVENTS_TABLE, {EID_COL, ACTIVITY_COL, TIMESTAMP_COL})
    rows = _rows(
        ocel,
        f"SELECT e.{_EID}, e.{_TIME}, e.{ident(ACTIVITY_COL)}, r.{_OID}, o.{_OTYPE}, r.{ident(E2O_QUALIFIER)}"
        f"{''.join(f', e.{ident(c)}' for c in columns)} "
        f"FROM {ident(EVENTS_TABLE)} e JOIN {ident(E2O_TABLE)} r ON r.{_EID} = e.{_EID} "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = r.{_OID} "
        f"ORDER BY e.{_TIME}, e.{_EID}, r.{_OID}, r.{ident(E2O_QUALIFIER)}",
    )
    for index, (_, group) in enumerate(groupby(rows, key=lambda row: row[0])):  # rows of one event are adjacent
        event_rows = list(group)
        _, time, activity, _, _, _, *values = event_rows[0]
        relations = tuple(Relation(ObjectRef(str(row[3]), str(row[4])), row[5]) for row in event_rows)
        attributes = {column: value for column, value in zip(columns, values, strict=True) if value is not None}
        yield (time, rank, index), StreamItem(Event(str(activity), relations, attributes), time)


def _attribute_updates(ocel: OCEL, rank: int) -> Iterator[tuple[Any, StreamItem]]:
    core = {OID_COL, TIMESTAMP_COL, OBJECT_CHANGED_FIELD}
    columns = [
        str(row[0]) for row in ocel.sql(f"DESCRIBE {ident(OBJECT_CHANGES_TABLE)}").fetchall() if row[0] not in core
    ]
    field = ident(OBJECT_CHANGED_FIELD)
    rows = _rows(
        ocel,
        f"SELECT c.{_TIME}, c.{_OID}, o.{_OTYPE}, c.{field}{''.join(f', c.{ident(c)}' for c in columns)} "
        f"FROM {ident(OBJECT_CHANGES_TABLE)} c JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = c.{_OID} "
        f"ORDER BY c.{_TIME}, c.{_OID}, c.{field}",
    )
    index = 0
    for time, object_id, object_type, changed, *values in rows:
        obj = ObjectRef(str(object_id), str(object_type))
        by_column = dict(zip(columns, values, strict=True))
        changes = (
            [(str(changed), by_column.get(str(changed)))]
            if changed is not None
            else [(column, value) for column, value in by_column.items() if value is not None]
        )
        for attribute, value in changes:
            yield (time, rank, index), StreamItem(AttributeUpdate(obj, attribute, value), time)
            index += 1


def _o2o_updates(ocel: OCEL, rank: int) -> Iterator[tuple[Any, StreamItem]]:
    source, target, qualifier = ident(O2O_SOURCE_ID), ident(O2O_TARGET_ID), ident(O2O_QUALIFIER)
    rows = _rows(
        ocel,
        f"SELECT f.time, x.{source}, s.{_OTYPE}, x.{target}, t.{_OTYPE}, x.{qualifier} "
        f"FROM {ident(O2O_TABLE)} x JOIN ({_FIRST_SEEN}) f ON f.oid = x.{source} "
        f"JOIN {ident(OBJECTS_TABLE)} s ON s.{_OID} = x.{source} "
        f"JOIN {ident(OBJECTS_TABLE)} t ON t.{_OID} = x.{target} "
        f"ORDER BY f.time, x.{source}, x.{target}, x.{qualifier}",
    )
    for index, (time, source_id, source_type, target_id, target_type, rel) in enumerate(rows):
        update = O2OUpdate(
            ObjectRef(str(source_id), str(source_type)), ObjectRef(str(target_id), str(target_type)), rel
        )
        yield (time, rank, index), StreamItem(update, time)
