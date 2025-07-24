import sys
import types
from pathlib import Path
import pytest

# Ensure project root is on the path so local modules can be imported when
# running `pytest` from any location.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Provide a dummy soundfile module if it's missing so that correct_times can be imported
if 'soundfile' not in sys.modules:
    sys.modules['soundfile'] = types.ModuleType('soundfile')

from correct_times import time_to_seconds

@pytest.mark.parametrize(
    'timestamp, expected',
    [
        ("00:00:00,000", 0.0),
        ("00:01:02,003", 62.003),
        ("01:02:03.123", 3723.123),
        ("10:20:30,400", 37230.4),
        ("23:59:59,999", 86399.999),
    ],
)
def test_time_to_seconds_valid(timestamp, expected):
    assert pytest.approx(time_to_seconds(timestamp), rel=1e-6) == expected

@pytest.mark.parametrize(
    'timestamp',
    [
        "not a time",
        "01:02:03",  # missing milliseconds
        "25:00:00,000",  # invalid hour
        "12:60:00,000",  # invalid minute
        "12:00:60,000",  # invalid second
    ],
)
def test_time_to_seconds_invalid(timestamp):
    with pytest.raises(ValueError):
        time_to_seconds(timestamp)
