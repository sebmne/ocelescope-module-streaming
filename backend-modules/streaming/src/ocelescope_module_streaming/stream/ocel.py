"""Replay of an Ocelescope OCEL as an object-centric event stream.

This and the API layer are the only modules that depend on Ocelescope and DuckDB.

Order of the items:
    Items are ordered by timestamp. Items with equal timestamps are ordered by kind (events, then
    attribute updates, then O2O updates, as in the implementation of Liss et al.) and then by
    identifier, so every replay of a log yields the same stream. The relations of an event are
    ordered by object id and qualifier.

Conventions for information an OCEL does not provide:
    - O2O relations carry no timestamp. Each is placed at the first event of its source object,
      as in the implementation of Liss et al.; relations whose source has no event are skipped.
    - Events without related objects are skipped.
    - An object change without a field sets every attribute that has a value.
    - Attribute columns of the objects table (values without a timestamp) are not replayed.

The log is read in batches, with one cursor per item kind, so the memory of a replay does not
depend on the size of the log. The result is well-formed: timestamps never decrease, and every
object has the single type the objects table gives it.
"""

import heapq
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import duckdb
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
from ocelescope.util.sql import ident, set_utc

from ocelescope_module_streaming.stream.items import (
    AttributeUpdate,
    Event,
    O2OUpdate,
    Relation,
    StreamItem,
    Value,
)
from ocelescope_module_streaming.stream.options import StreamOptions

BATCH_SIZE = 10_000
"""Number of rows fetched per database round trip."""

# Rank of each item kind among items with equal timestamps.
_EVENT, _ATTRIBUTE_UPDATE, _O2O_UPDATE = 0, 1, 2

# An item with its sort key: (timestamp, kind rank, index within kind).
_Keyed = tuple[tuple[datetime, int, int], StreamItem]
_Query = Callable[[str], duckdb.DuckDBPyConnection]

_EID, _OID, _OTYPE = ident(EID_COL), ident(OID_COL), ident(OTYPE_COL)
_TIME, _ACTIVITY = ident(TIMESTAMP_COL), ident(ACTIVITY_COL)


@contextmanager
def ocel_stream(ocel: OCEL, options: StreamOptions | None = None) -> Iterator[Iterator[StreamItem]]:
    """Opens an OCEL as a stream.

    Args:
        ocel: The event log. It stays open when the context exits.
        options: The item kinds to include; by default all of them.

    Yields:
        An iterator over the stream items. The database cursors are closed when the context exits.
    """
    options = options or StreamOptions()
    cursors: list[duckdb.DuckDBPyConnection] = []

    def query(sql: str) -> duckdb.DuckDBPyConnection:
        cursor = ocel.con.cursor()
        cursors.append(cursor)
        set_utc(cursor)
        cursor.execute(sql)
        return cursor

    try:
        kinds: list[Iterator[_Keyed]] = []
        if options.events:
            columns = _attribute_columns(ocel, EVENTS_TABLE, {EID_COL, ACTIVITY_COL, TIMESTAMP_COL})
            kinds.append(_events(query, columns))
        if options.attribute_updates:
            columns = _attribute_columns(ocel, OBJECT_CHANGES_TABLE, {OID_COL, TIMESTAMP_COL, OBJECT_CHANGED_FIELD})
            kinds.append(_attribute_updates(query, columns))
        if options.o2o_updates:
            kinds.append(_o2o_updates(query))
        # Sort keys are unique, so the merge never compares the items themselves.
        yield (item for _, item in heapq.merge(*kinds))
    finally:
        for cursor in cursors:
            cursor.close()


def stream_length(ocel: OCEL, options: StreamOptions | None = None) -> int:
    """Returns the number of items `ocel_stream` yields, for progress reporting.

    An object change without a field is counted once, although it may yield several attribute
    updates, so the result can be lower than the actual length.
    """
    options = options or StreamOptions()
    counts: list[str] = []
    if options.events:
        counts.append(
            f"SELECT count(DISTINCT r.{_EID}) FROM {ident(E2O_TABLE)} r "
            f"JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = r.{_OID} "
            f"JOIN {ident(EVENTS_TABLE)} e ON e.{_EID} = r.{_EID}"
        )
    if options.attribute_updates:
        counts.append(
            f"SELECT count(*) FROM {ident(OBJECT_CHANGES_TABLE)} c JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = c.{_OID}"
        )
    if options.o2o_updates:
        source, target = ident(O2O_SOURCE_ID), ident(O2O_TARGET_ID)
        counts.append(
            f"SELECT count(*) FROM {ident(O2O_TABLE)} x "
            f"JOIN {ident(OBJECTS_TABLE)} s ON s.{_OID} = x.{source} "
            f"JOIN {ident(OBJECTS_TABLE)} t ON t.{_OID} = x.{target} "
            f"WHERE x.{source} IN (SELECT r.{_OID} FROM {ident(E2O_TABLE)} r "
            f"JOIN {ident(EVENTS_TABLE)} e ON e.{_EID} = r.{_EID})"
        )
    return sum(int(ocel.sql(sql).fetchall()[0][0]) for sql in counts)


def _attribute_columns(ocel: OCEL, table: str, core: set[str]) -> list[str]:
    """Returns the columns of `table` that hold attribute values, in table order."""
    rows = ocel.sql(f"DESCRIBE {ident(table)}").fetchall()
    return [str(row[0]) for row in rows if row[0] not in core]


def _rows(cursor: duckdb.DuckDBPyConnection) -> Iterator[tuple[Any, ...]]:
    while batch := cursor.fetchmany(BATCH_SIZE):
        yield from batch


def _attributes(names: Sequence[str], values: Sequence[Any]) -> dict[str, Value]:
    return {name: value for name, value in zip(names, values, strict=True) if value is not None}


def _events(query: _Query, columns: list[str]) -> Iterator[_Keyed]:
    attribute_select = "".join(f", e.{ident(column)}" for column in columns)
    cursor = query(
        f"SELECT e.{_EID}, e.{_TIME}, e.{_ACTIVITY}, r.{_OID}, o.{_OTYPE}, r.{ident(E2O_QUALIFIER)}{attribute_select} "
        f"FROM {ident(EVENTS_TABLE)} e "
        f"JOIN {ident(E2O_TABLE)} r ON r.{_EID} = e.{_EID} "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = r.{_OID} "
        f"ORDER BY e.{_TIME}, e.{_EID}, r.{_OID}, r.{ident(E2O_QUALIFIER)}"
    )
    # Rows are ordered by event, so the rows of one event are adjacent.
    index = 0
    current: tuple[Any, ...] | None = None
    relations: list[Relation] = []
    for row in _rows(cursor):
        if current is not None and row[0] != current[0]:
            yield (current[1], _EVENT, index), _event(current, relations, columns)
            index += 1
            relations = []
        current = row
        relations.append(Relation(str(row[3]), str(row[4]), "" if row[5] is None else str(row[5])))
    if current is not None:
        yield (current[1], _EVENT, index), _event(current, relations, columns)


def _event(row: tuple[Any, ...], relations: list[Relation], columns: list[str]) -> StreamItem:
    content = Event(activity=str(row[2]), relations=tuple(relations), attributes=_attributes(columns, row[6:]))
    return StreamItem(content, row[1])


def _attribute_updates(query: _Query, columns: list[str]) -> Iterator[_Keyed]:
    changed_field = ident(OBJECT_CHANGED_FIELD)
    attribute_select = "".join(f", c.{ident(column)}" for column in columns)
    cursor = query(
        f"SELECT c.{_TIME}, c.{_OID}, o.{_OTYPE}, c.{changed_field}{attribute_select} "
        f"FROM {ident(OBJECT_CHANGES_TABLE)} c "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{_OID} = c.{_OID} "
        f"ORDER BY c.{_TIME}, c.{_OID}, c.{changed_field}"
    )
    index = 0
    for row in _rows(cursor):
        time, oid, otype, changed = row[0], str(row[1]), str(row[2]), row[3]
        values = dict(zip(columns, row[4:], strict=True))
        if changed is None:
            updates = list(_attributes(columns, row[4:]).items())
        else:
            updates = [(str(changed), values.get(str(changed)))]
        for attribute, value in updates:
            yield (time, _ATTRIBUTE_UPDATE, index), StreamItem(AttributeUpdate(oid, otype, attribute, value), time)
            index += 1


def _o2o_updates(query: _Query) -> Iterator[_Keyed]:
    source, target, qualifier = ident(O2O_SOURCE_ID), ident(O2O_TARGET_ID), ident(O2O_QUALIFIER)
    cursor = query(
        f"WITH first_seen AS ("
        f"  SELECT r.{_OID} AS oid, MIN(e.{_TIME}) AS time "
        f"  FROM {ident(E2O_TABLE)} r JOIN {ident(EVENTS_TABLE)} e ON e.{_EID} = r.{_EID} GROUP BY r.{_OID}"
        f") "
        f"SELECT f.time, x.{source}, s.{_OTYPE}, x.{target}, t.{_OTYPE}, x.{qualifier} "
        f"FROM {ident(O2O_TABLE)} x "
        f"JOIN first_seen f ON f.oid = x.{source} "
        f"JOIN {ident(OBJECTS_TABLE)} s ON s.{_OID} = x.{source} "
        f"JOIN {ident(OBJECTS_TABLE)} t ON t.{_OID} = x.{target} "
        f"ORDER BY f.time, x.{source}, x.{target}, x.{qualifier}"
    )
    for index, row in enumerate(_rows(cursor)):
        update = O2OUpdate(str(row[1]), str(row[2]), "" if row[5] is None else str(row[5]), str(row[3]), str(row[4]))
        yield (row[0], _O2O_UPDATE, index), StreamItem(update, row[0])
