"""
Quality scorer — 7 signals, real-time, letter grades S–F.
"""

from __future__ import annotations

from dataclasses import dataclass

from TrimP.db import db, now_iso


GRADE_THRESHOLDS = [
    ("S", 0.90),
    ("A", 0.80),
    ("B", 0.65),
    ("C", 0.50),
    ("D", 0.35),
    ("F", 0.0),
]


@dataclass
class QualityReport:
    session_id: str
    conciseness: float       # 1.0 = perfectly concise
    compression: float       # ratio of tokens saved / tokens before
    context_utilization: float  # tokens used / context window
    model_routing: float     # fraction of turns optimally routed
    loop_rate: float         # 1.0 = no loops detected (inverted)
    cache_hit_rate: float    # file re-reads that were cache hits
    overall: float
    grade: str

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "conciseness": self.conciseness,
            "compression": self.compression,
            "context_utilization": self.context_utilization,
            "model_routing": self.model_routing,
            "loop_rate": self.loop_rate,
            "cache_hit_rate": self.cache_hit_rate,
            "overall": self.overall,
            "grade": self.grade,
        }


def score_session(session_id: str) -> QualityReport:
    with db() as conn:
        session = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        turns = conn.execute(
            "SELECT tokens_in, tokens_out, tokens_saved FROM turns WHERE session_id=?",
            (session_id,),
        ).fetchall()
        compressions = conn.execute(
            "SELECT tokens_before, tokens_after FROM compressions WHERE session_id=?",
            (session_id,),
        ).fetchall()
        routing = conn.execute(
            "SELECT was_optimal FROM model_routing WHERE session_id=?",
            (session_id,),
        ).fetchall()
        loops = conn.execute(
            "SELECT COUNT(*) as c FROM loop_detections WHERE session_id=?",
            (session_id,),
        ).fetchone()
        budgets = conn.execute(
            "SELECT context_window, tokens_used FROM token_budgets WHERE session_id=? ORDER BY snapshot_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        file_reads = conn.execute(
            """SELECT COUNT(*) as total FROM compressions
               WHERE session_id=? AND compressor='delta'""",
            (session_id,),
        ).fetchone()
        cache_hits = conn.execute(
            """SELECT COUNT(*) as hits FROM compressions
               WHERE session_id=? AND compressor='delta' AND tokens_after < tokens_before""",
            (session_id,),
        ).fetchone()

    # 1. Conciseness: avg verbosity score inverted
    total_in = sum(t["tokens_in"] for t in turns) or 1
    total_saved = sum(t["tokens_saved"] for t in turns)
    conciseness = min(1.0, 0.5 + (total_saved / total_in) * 0.5)

    # 2. Compression effectiveness
    if compressions:
        total_before = sum(c["tokens_before"] for c in compressions) or 1
        total_after = sum(c["tokens_after"] for c in compressions)
        compression = max(0.0, 1.0 - (total_after / total_before))
    else:
        compression = 0.0

    # 3. Context utilization (headroom — lower utilization = better score)
    if budgets:
        used = budgets["tokens_used"]
        window = budgets["context_window"] or 200_000
        util = used / window
        context_utilization = max(0.0, 1.0 - max(0.0, util - 0.5) * 2)  # penalize >50% usage
    else:
        context_utilization = 0.8

    # 4. Model routing accuracy
    if routing:
        optimal = sum(1 for r in routing if r["was_optimal"])
        model_routing = optimal / len(routing)
    else:
        model_routing = 0.75  # assume ok if no data

    # 5. Loop rate (inverted — fewer loops = higher score)
    turn_count = len(turns) or 1
    loop_count = loops["c"] if loops else 0
    loop_rate = max(0.0, 1.0 - (loop_count / turn_count) * 2)

    # 6. Cache hit rate
    total_file_reads = file_reads["total"] if file_reads else 0
    hits = cache_hits["hits"] if cache_hits else 0
    cache_hit_rate = (hits / total_file_reads) if total_file_reads > 0 else 0.8

    # Weighted overall
    overall = (
        conciseness         * 0.20 +
        compression         * 0.25 +
        context_utilization * 0.20 +
        model_routing       * 0.15 +
        loop_rate           * 0.10 +
        cache_hit_rate      * 0.10
    )
    grade = _grade(overall)

    report = QualityReport(
        session_id=session_id,
        conciseness=conciseness,
        compression=compression,
        context_utilization=context_utilization,
        model_routing=model_routing,
        loop_rate=loop_rate,
        cache_hit_rate=cache_hit_rate,
        overall=overall,
        grade=grade,
    )

    # Persist to DB
    _persist(report)
    _update_session_grade(session_id, grade)

    return report


def _grade(score: float) -> str:
    for g, threshold in GRADE_THRESHOLDS:
        if score >= threshold:
            return g
    return "F"


def _persist(r: QualityReport) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO quality_scores
               (session_id, conciseness_ratio, compression_effectiveness,
                context_utilization, model_routing_accuracy, loop_detection_rate,
                cache_hit_rate, overall_score, grade, scored_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                r.session_id, r.conciseness, r.compression, r.context_utilization,
                r.model_routing, r.loop_rate, r.cache_hit_rate, r.overall, r.grade, now_iso(),
            ),
        )


def _update_session_grade(session_id: str, grade: str) -> None:
    with db() as conn:
        conn.execute("UPDATE sessions SET quality_grade=? WHERE id=?", (grade, session_id))


def score_to_bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)
