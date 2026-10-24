from mobiletester.android.capture import crash_summary, new_lines

JAVA_CRASH = """--------- beginning of crash
10-23 15:04:31.120  4321  4321 E AndroidRuntime: FATAL EXCEPTION: main
10-23 15:04:31.120  4321  4321 E AndroidRuntime: Process: com.example.notes, PID: 4321
10-23 15:04:31.120  4321  4321 E AndroidRuntime: java.lang.IllegalStateException: Fragment not attached
10-23 15:04:31.120  4321  4321 E AndroidRuntime: \tat androidx.fragment.app.Fragment.requireContext(Fragment.java:900)
""".splitlines()

NATIVE_CRASH = """10-23 15:10:02.500  7777  7790 F libc    : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR) in tid 7790
10-23 15:10:02.600  7800  7800 F DEBUG   : Process: com.example.game
""".splitlines()


def test_new_lines_since_last_read():
    assert new_lines(0, ["a", "b"]) == (["a", "b"], 2)
    assert new_lines(2, ["a", "b", "c"]) == (["c"], 3)
    assert new_lines(2, ["a", "b"]) == ([], 2)


def test_cleared_buffer_starts_over():
    assert new_lines(5, ["x"]) == (["x"], 1)


def test_java_crash_summary():
    assert crash_summary(JAVA_CRASH) == "com.example.notes: java.lang.IllegalStateException: Fragment not attached"


def test_native_crash_summary():
    assert crash_summary(NATIVE_CRASH).startswith("com.example.game: Fatal signal 11 (SIGSEGV)")
