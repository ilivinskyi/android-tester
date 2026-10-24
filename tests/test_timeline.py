import shutil
import subprocess

import pytest

from mobiletester.core.clip import build_timeline, concat_listing, video_position

# Two chunks; the second started 2.6 s after the first one's 180 s ended (screenrecord restart gap).
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


def test_still_screen_at_chunk_end_does_not_shift_the_video():
    # Chunk 1's last frame came at 163 s (screen still afterwards); chunk 2 started at wall 1181.5.
    timeline = {"chunks": build_timeline([(1000.0, 163.0), (1181.5, 40.0)])}
    assert timeline["chunks"][0]["span"] == 181.5
    assert timeline["chunks"][1]["video_start"] == 181.5
    # 10 s into chunk 2 is 191.5 s into the joined video, not 173 s.
    assert video_position(timeline, 1191.5) == 191.5
    # The still stretch at the end of chunk 1 maps inside chunk 1.
    assert video_position(timeline, 1170.0) == 170.0


def test_concat_listing_gives_every_chunk_its_span(tmp_path):
    chunks = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    listing = concat_listing(chunks, [181.5, 40.0]).splitlines()
    assert listing[1] == "duration 181.500" and listing[3] == "duration 40.000"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="needs ffmpeg")
def test_ffmpeg_holds_the_last_frame_for_the_span(tmp_path):
    clips = []
    for name, seconds in (("a", 2), ("b", 2)):
        clip = tmp_path / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"testsrc=size=64x64:rate=10:duration={seconds}", "-c:v", "libx264", str(clip)], check=True)
        clips.append(clip)
    listing = tmp_path / "list.txt"
    listing.write_text(concat_listing(clips, [5.0, 2.0]), encoding="utf-8")
    out = tmp_path / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(out)], check=True)
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                     "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout)
    assert duration == pytest.approx(7.0, abs=0.3)
