"""Read one option 3 instance directory and apply the four input checks.

The loader never repairs data.  Any failed check raises InputError with a
message that names the file and the column, and the command line turns that
into a nonzero exit without writing decision.json.
"""

import csv
import math
from pathlib import Path

# Required files and columns (DATA_DICTIONARY.md, schema version 4).
# No option 3 column is nullable.
SCHEMA = {
    "depots.csv": {"node_id": "string", "x": "number", "y": "number"},
    "customers.csv": {
        "customer_id": "string",
        "x": "number",
        "y": "number",
        "demand": "integer",
        "service_time": "integer",
        "window_start": "integer",
        "window_end": "integer",
    },
    "vehicles.csv": {
        "vehicle_id": "string",
        "capacity": "integer",
        "shift_start": "integer",
        "shift_end": "integer",
    },
    "travel_times.csv": {"from_id": "string", "to_id": "string", "travel_time": "number"},
}


class InputError(Exception):
    """Raised when an instance fails one of the input checks."""


def _convert(text, kind, file_name, column, row_number):
    _where = f"{file_name}, column '{column}', row {row_number}"
    if text is None or text.strip() == "":
        raise InputError(f"{_where}: value is empty but the column is not nullable")
    text = text.strip()
    if kind == "string":
        return text
    try:
        _value = float(text)
    except ValueError:
        raise InputError(f"{_where}: '{text}' is not a {kind}") from None
    if not math.isfinite(_value):
        raise InputError(f"{_where}: '{text}' is not a finite {kind}")
    if kind == "integer":
        if not _value.is_integer():
            raise InputError(f"{_where}: '{text}' is not an integer")
        return int(_value)
    return _value


def read_table(directory, file_name):
    """Check 1 (file and columns present) and check 2 (types, no empties)."""
    _path = Path(directory) / file_name
    if not _path.is_file():
        raise InputError(f"{file_name}: required file is missing from {directory}")
    with open(_path, newline="", encoding="utf-8-sig") as _f:
        _reader = csv.DictReader(_f)
        _header = [h.strip() for h in (_reader.fieldnames or [])]
        for _column in SCHEMA[file_name]:
            if _column not in _header:
                raise InputError(f"{file_name}, column '{_column}': required column is missing")
        _rows = []
        for _number, _raw in enumerate(_reader, start=2):  # row 1 is the header
            _raw = {k.strip(): v for k, v in _raw.items() if k is not None}
            _rows.append({
                _column: _convert(_raw.get(_column), _kind, file_name, _column, _number)
                for _column, _kind in SCHEMA[file_name].items()
            })
    return _rows


def _unique(rows, file_name, column):
    _seen = set()
    for _row in rows:
        if _row[column] in _seen:
            raise InputError(f"{file_name}, column '{column}': identifier '{_row[column]}' is repeated")
        _seen.add(_row[column])


def load_instance(directory):
    """Return a dictionary with depot, customers, vehicles, and travel lookups.

    customers and vehicles are dictionaries keyed by identifier, and travel is
    a dictionary keyed by (from_id, to_id), so identifiers are matched by
    value, never by row position.
    """
    _depots = read_table(directory, "depots.csv")
    _customers = read_table(directory, "customers.csv")
    _vehicles = read_table(directory, "vehicles.csv")
    _travel = read_table(directory, "travel_times.csv")

    if len(_depots) != 1:
        raise InputError(f"depots.csv, column 'node_id': expected exactly one depot, found {len(_depots)}")
    _unique(_customers, "customers.csv", "customer_id")
    _unique(_vehicles, "vehicles.csv", "vehicle_id")
    _depot = _depots[0]["node_id"]
    if any(_c["customer_id"] == _depot for _c in _customers):
        raise InputError(f"customers.csv, column 'customer_id': '{_depot}' is also the depot identifier")

    # Check 4: durations positive; plus the sign and interval rules that make
    # the data meaningful.  Nothing is silently replaced.
    for _number, _c in enumerate(_customers, start=2):
        if _c["service_time"] <= 0:
            raise InputError(f"customers.csv, column 'service_time', row {_number}: must be positive")
        if _c["demand"] < 0:
            raise InputError(f"customers.csv, column 'demand', row {_number}: must not be negative")
        if _c["window_start"] > _c["window_end"]:
            raise InputError(f"customers.csv, column 'window_end', row {_number}: window ends before it starts")
    for _number, _v in enumerate(_vehicles, start=2):
        if _v["capacity"] < 0:
            raise InputError(f"vehicles.csv, column 'capacity', row {_number}: must not be negative")
        if _v["shift_start"] >= _v["shift_end"]:
            raise InputError(f"vehicles.csv, column 'shift_end', row {_number}: shift ends before it starts")

    # Check 3: every identifier referenced from travel_times.csv exists, and
    # every ordered pair of locations has a row.
    _nodes = [_depot] + [_c["customer_id"] for _c in _customers]
    _node_set = set(_nodes)
    _times = {}
    for _number, _row in enumerate(_travel, start=2):
        for _column in ("from_id", "to_id"):
            if _row[_column] not in _node_set:
                raise InputError(
                    f"travel_times.csv, column '{_column}', row {_number}: "
                    f"'{_row[_column]}' is not in depots.csv or customers.csv"
                )
        if _row["travel_time"] < 0:
            raise InputError(f"travel_times.csv, column 'travel_time', row {_number}: must not be negative")
        if (_row["from_id"], _row["to_id"]) in _times:
            raise InputError(
                f"travel_times.csv, columns 'from_id'/'to_id', row {_number}: "
                f"{_row['from_id']} -> {_row['to_id']} appears more than once"
            )
        _times[(_row["from_id"], _row["to_id"])] = _row["travel_time"]
    for _a in _nodes:
        for _b in _nodes:
            if (_a, _b) not in _times:
                raise InputError(f"travel_times.csv, columns 'from_id'/'to_id': no row for {_a} -> {_b}")

    _locations = {_depot: (_depots[0]["x"], _depots[0]["y"])}
    _locations.update({_c["customer_id"]: (_c["x"], _c["y"]) for _c in _customers})
    return {
        "directory": str(directory),
        "depot": _depot,
        "customers": {_c["customer_id"]: _c for _c in _customers},
        "vehicles": {_v["vehicle_id"]: _v for _v in _vehicles},
        "travel": _times,
        "locations": _locations,
    }
