"""
Terminal dashboard — Textual TUI.
Launch with `TrimP dashboard` (terminal mode).
"""

from __future__ import annotations

from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import (
    DataTable, Footer, Header, Label, ProgressBar, Rule, Static, TabbedContent, TabPane,
)

from TrimP.db import db
from TrimP.quality import score_session, score_to_bar
from TrimP.session import get_or_create_session


class GradeWidget(Static):
    grade: reactive[str] = reactive("?")
    score: reactive[float] = reactive(0.0)

    GRADE_COLORS = {"S": "bright_green", "A": "green", "B": "yellow", "C": "orange3", "D": "red", "F": "red3"}

    def render(self) -> str:
        c = self.GRADE_COLORS.get(self.grade, "white")
        bar = score_to_bar(self.score, 20)
        return f"[{c}][bold]{self.grade}[/bold] {self.score:.0%}[/{c}]\n{bar}"


class MetricCard(Static):
    def __init__(self, label: str, value: str, color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._color = color

    def render(self) -> str:
        return f"[dim]{self._label}[/dim]\n[{self._color}][bold]{self._value}[/bold][/{self._color}]"

    def update_value(self, value: str) -> None:
        self._value = value
        self.refresh()


class TokenOptimizerDashboard(App):
    """Full terminal dashboard for TrimP."""

    CSS = """
    Screen { background: $surface; }
    Header { background: $accent; }
    Footer { background: $accent-darken-1; }

    #top-bar {
        height: 5;
        padding: 0 2;
        background: $primary-darken-2;
    }

    GradeWidget {
        width: 24;
        height: 4;
        padding: 0 1;
        border: solid $accent;
        margin: 0 1;
    }

    MetricCard {
        width: 20;
        height: 4;
        padding: 0 1;
        border: solid $primary;
        margin: 0 1;
    }

    #compression-table { height: 15; margin: 1 2; }
    #sessions-table    { height: 20; margin: 1 2; }
    #quality-table     { height: 12; margin: 1 2; }
    #loops-pane        { height: 10; margin: 1 2; }

    .section-title {
        color: $accent;
        text-style: bold;
        padding: 0 2;
        margin-top: 1;
    }

    #status-bar {
        height: 1;
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 2;
    }
    """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
        ("t", "toggle_theme", "Theme"),
        ("s", "show_savings", "Savings"),
    ]

    TITLE = "TrimP — Copilot Token Optimizer"
    SUB_TITLE = "Real-time token analytics"

    def __init__(self, session_id: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id or get_or_create_session()
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="top-bar"):
            yield GradeWidget(id="grade-widget")
            yield MetricCard("Tokens Saved", "—", "green", id="card-saved")
            yield MetricCard("Compressions", "—", "cyan", id="card-compressions")
            yield MetricCard("Archives", "—", "magenta", id="card-archives")
            yield MetricCard("Loops", "—", "red", id="card-loops")

        with TabbedContent():
            with TabPane("📦 Compression", id="tab-compression"):
                yield Label("Compression by Component", classes="section-title")
                yield DataTable(id="compression-table")

            with TabPane("📊 Quality", id="tab-quality"):
                yield Label("Quality Signals (7)", classes="section-title")
                yield DataTable(id="quality-table")

            with TabPane("🗄️ Sessions", id="tab-sessions"):
                yield Label("Recent Sessions", classes="section-title")
                yield DataTable(id="sessions-table")

            with TabPane("🔄 Live", id="tab-live"):
                yield Label("Live Compression Events", classes="section-title")
                yield ScrollableContainer(DataTable(id="live-table"))

            with TabPane("🩺 Health", id="tab-health"):
                yield Label("System Health", classes="section-title")
                yield ScrollableContainer(Static(id="health-content"))

        yield Static(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_tables()
        self._refresh_data()
        self._refresh_timer = self.set_interval(5, self._refresh_data)

    def _setup_tables(self) -> None:
        comp_table: DataTable = self.query_one("#compression-table", DataTable)
        comp_table.add_columns("Compressor", "Events", "Before", "After", "Saved", "Ratio")

        qual_table: DataTable = self.query_one("#quality-table", DataTable)
        qual_table.add_columns("Signal", "Score", "Bar", "Grade")

        sess_table: DataTable = self.query_one("#sessions-table", DataTable)
        sess_table.add_columns("Session", "Started", "Tokens Saved", "Grade", "Status")

        live_table: DataTable = self.query_one("#live-table", DataTable)
        live_table.add_columns("Time", "Compressor", "Before", "After", "Saved")

    def _refresh_data(self) -> None:
        try:
            report = score_session(self.session_id)
            self._update_grade(report)
            self._update_compression_table()
            self._update_quality_table(report)
            self._update_sessions_table()
            self._update_live_table()
            self._update_health()
            self._update_status()
        except Exception as e:
            self.query_one("#status-bar", Static).update(f"Error: {e}")

    def _update_grade(self, report) -> None:
        widget: GradeWidget = self.query_one("#grade-widget", GradeWidget)
        widget.grade = report.grade
        widget.score = report.overall

        with db() as conn:
            sess = conn.execute("SELECT * FROM sessions WHERE id=?", (self.session_id,)).fetchone()
            loops = conn.execute(
                "SELECT COUNT(*) as c FROM loop_detections WHERE session_id=?", (self.session_id,)
            ).fetchone()["c"]
            arcs = conn.execute(
                "SELECT COUNT(*) as c FROM archives WHERE session_id=?", (self.session_id,)
            ).fetchone()["c"]
            compressions = conn.execute(
                "SELECT COUNT(*) as c FROM compressions WHERE session_id=?", (self.session_id,)
            ).fetchone()["c"]

        saved = sess["tokens_saved"] if sess else 0
        self.query_one("#card-saved", MetricCard).update_value(f"{saved:,}")
        self.query_one("#card-compressions", MetricCard).update_value(str(compressions))
        self.query_one("#card-archives", MetricCard).update_value(str(arcs))
        self.query_one("#card-loops", MetricCard).update_value(str(loops))

    def _update_compression_table(self) -> None:
        t: DataTable = self.query_one("#compression-table", DataTable)
        t.clear()
        with db() as conn:
            rows = conn.execute(
                """SELECT compressor, COUNT(*) as events,
                          SUM(tokens_before) as t_before, SUM(tokens_after) as t_after
                   FROM compressions WHERE session_id=?
                   GROUP BY compressor ORDER BY (SUM(tokens_before)-SUM(tokens_after)) DESC""",
                (self.session_id,),
            ).fetchall()
        for row in rows:
            before = row["t_before"] or 1
            after = row["t_after"] or 0
            saved = before - after
            t.add_row(row["compressor"], str(row["events"]),
                      f"{before:,}", f"{after:,}", f"{saved:,}", f"{saved/before:.0%}")

    def _update_quality_table(self, report) -> None:
        t: DataTable = self.query_one("#quality-table", DataTable)
        t.clear()
        signals = [
            ("Conciseness", report.conciseness),
            ("Compression Effectiveness", report.compression),
            ("Context Utilization", report.context_utilization),
            ("Model Routing Accuracy", report.model_routing),
            ("Loop-free Rate", report.loop_rate),
            ("Cache Hit Rate", report.cache_hit_rate),
        ]
        for name, score in signals:
            bar = score_to_bar(score, 15)
            t.add_row(name, f"{score:.0%}", bar, _grade_letter(score))

    def _update_sessions_table(self) -> None:
        t: DataTable = self.query_one("#sessions-table", DataTable)
        t.clear()
        with db() as conn:
            rows = conn.execute(
                """SELECT id, started_at, tokens_saved, quality_grade, status
                   FROM sessions ORDER BY started_at DESC LIMIT 20""",
            ).fetchall()
        for row in rows:
            t.add_row(
                row["id"][:16] + "...",
                row["started_at"][:16] if row["started_at"] else "?",
                f"{row['tokens_saved'] or 0:,}",
                row["quality_grade"] or "?",
                row["status"] or "?",
            )

    def _update_live_table(self) -> None:
        t: DataTable = self.query_one("#live-table", DataTable)
        t.clear()
        with db() as conn:
            rows = conn.execute(
                """SELECT compressed_at, compressor, tokens_before, tokens_after
                   FROM compressions WHERE session_id=?
                   ORDER BY compressed_at DESC LIMIT 30""",
                (self.session_id,),
            ).fetchall()
        for row in rows:
            saved = (row["tokens_before"] or 0) - (row["tokens_after"] or 0)
            t.add_row(
                row["compressed_at"][:19] if row["compressed_at"] else "?",
                row["compressor"],
                str(row["tokens_before"] or 0),
                str(row["tokens_after"] or 0),
                f"{saved:,}",
            )

    def _update_health(self) -> None:
        from TrimP.commands.doctor import REQUIRED_PACKAGES
        import importlib
        lines: list[str] = []
        for pkg in REQUIRED_PACKAGES:
            try:
                importlib.import_module(pkg)
                lines.append(f"✓ {pkg}")
            except ImportError:
                lines.append(f"✗ {pkg} (missing)")
        self.query_one("#health-content", Static).update("\n".join(lines))

    def _update_status(self) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.query_one("#status-bar", Static).update(
            f"Session: {self.session_id[:16]}...  Updated: {ts}  Press [r] refresh  [q] quit"
        )

    def action_refresh(self) -> None:
        self._refresh_data()

    def action_toggle_theme(self) -> None:
        self.dark = not self.dark

    def action_show_savings(self) -> None:
        from TrimP.commands import savings
        savings.run(self.session_id)


def _grade_letter(score: float) -> str:
    if score >= 0.9: return "S"
    if score >= 0.8: return "A"
    if score >= 0.65: return "B"
    if score >= 0.5: return "C"
    if score >= 0.35: return "D"
    return "F"


def launch(session_id: str | None = None) -> None:
    app = TokenOptimizerDashboard(session_id=session_id)
    app.run()
