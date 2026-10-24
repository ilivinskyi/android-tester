from mobiletester.android import perf

# Captured from a Pixel 7a on Android 17.
GFXINFO = """Total frames rendered: 465
Janky frames: 17 (3.66%)
Janky frames (legacy): 34 (7.31%)
50th percentile: 7ms
90th percentile: 12ms
95th percentile: 21ms
99th percentile: 48ms
Number Missed Vsync: 0
50th gpu percentile: 3ms
"""

MEMINFO = """        TOTAL   248054   171084    42000      748   445580   334228    74316   256297
           TOTAL PSS:   248054            TOTAL RSS:   445580       TOTAL SWAP PSS:      748
"""

AM_START = """Starting: Intent { cmp=com.example.notes/.MainActivity }
Status: ok
LaunchState: COLD
Activity: com.example.notes/.MainActivity
TotalTime: 812
WaitTime: 830
Complete
"""


def test_gfxinfo():
    assert perf.parse_gfxinfo(GFXINFO) == {"frames": 465, "janky": 17, "janky_pct": 3.66,
                                           "p50_ms": 7, "p90_ms": 12, "p95_ms": 21, "p99_ms": 48}


def test_meminfo():
    assert perf.parse_meminfo(MEMINFO) == {"pss_kb": 248054, "rss_kb": 445580}


def test_meminfo_older_format_without_summary_line():
    assert perf.parse_meminfo("   TOTAL    98765    1234\n") == {"pss_kb": 98765}


def test_am_start():
    assert perf.parse_am_start(AM_START) == {"total_ms": 812, "wait_ms": 830, "launch_state": "COLD"}
