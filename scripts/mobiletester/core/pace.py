"""How fast a person acts, and what an action turned out to do. Shared by the Android and iOS drivers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pace:
    name: str
    think: tuple[float, float]       # pause before an action, seconds
    press_ms: tuple[int, int]        # finger down time for a tap
    long_press_ms: tuple[int, int]
    key_press_ms: tuple[int, int]    # keyboard keys are hit quicker than buttons
    key_gap: tuple[float, float]     # between keystrokes, seconds
    swipe_ms: tuple[int, int]


PACES = {
    "human": Pace("human", (0.4, 1.4), (60, 150), (700, 1000), (40, 90), (0.05, 0.2), (280, 520)),
    "slow": Pace("slow", (1.0, 2.5), (80, 180), (800, 1200), (60, 120), (0.12, 0.35), (400, 700)),
}


@dataclass
class Outcome:
    changed: bool | None = None   # None when not verified
    settled: bool | None = None
    crash: str | None = None      # summary of a crash written to the crash buffer during this action
    log_issues: list[str] = field(default_factory=list)  # the app's new errors and warnings in its log
    crash_command: str = "adt logcat crashes"  # where the full crash report is

    def warning(self) -> str | None:
        lines = []
        if self.crash:
            lines.append(f"CRASH right after this action: {self.crash}. Capture evidence now (observe, "
                         f"`{self.crash_command}`), note the action log time for the clip, then continue per the "
                         "session's crash rule.")
        elif self.changed is False:
            lines.append("WARNING: no visible change after this action. It may have hit dead space, a covering "
                         "overlay, or a stale position. Observe before continuing.")
        elif self.settled is False:
            lines.append("note: the screen was still changing after 5 s (animation, video or loading).")
        if self.log_issues:
            shown = "; ".join(self.log_issues[:3]) + (f" (+{len(self.log_issues) - 3} more)"
                                                       if len(self.log_issues) > 3 else "")
            lines.append(f"app log: {len(self.log_issues)} new issue(s) since the last action: {shown}. "
                         "Judge whether it explains what you see; many apps log harmless errors.")
        return "\n".join(lines) or None
