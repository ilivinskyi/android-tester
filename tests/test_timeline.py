from adtlib.capture import video_position

# Two chunks; the second started 2.6 s after the first ended (screenrecord restart gap).
TIMELINE = {"chunks": [
    {"wall_start": 1000.0, "video_start": 0.0, "duration": 180.0},
    {"wall_start": 1182.6, "video_start": 180.0, "duration": 60.0},
]}


def test_position_inside_first_chunk():
    assert video_position(TIMELINE, 1010.0) == 10.0


def test_position_in_second_chunk_skips_the_gap():
    assert video_position(TIMELINE, 1192.6) == 190.0


def test_position_in_gap_or_outside_is_none():
    assert video_position(TIMELINE, 1181.0) is None
    assert video_position(TIMELINE, 999.0) is None
    assert video_position(TIMELINE, 1300.0) is None
