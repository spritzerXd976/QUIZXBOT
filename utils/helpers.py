from typing import Optional
from config import BOT_USERNAME


def get_quiz_share_link(quiz_id: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=quiz_{quiz_id}"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"


def format_score_summary(correct: int, wrong: int, missed: int, score: float,
                          total: int, max_score: float, time_taken: float) -> str:
    percentage = (correct / total * 100) if total > 0 else 0
    return (
        f"✅ Correct: {correct}\n"
        f"❌ Wrong: {wrong}\n"
        f"⏭ Missed: {missed}\n"
        f"🎯 Score: {score:.1f} / {max_score:.1f}\n"
        f"📊 Percentage: {percentage:.1f}%\n"
        f"⏱ Time: {format_duration(time_taken)}"
    )


def get_rank_emoji(rank: int) -> str:
    emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    return emojis.get(rank, f"#{rank}")


def build_leaderboard_text(participants, quiz_title: str, total_questions: int) -> str:
    lines = [f"🏆 <b>Live Leaderboard</b>\n📝 {quiz_title}\n"]
    for i, p in enumerate(participants[:10]):
        pct = (p.correct / total_questions * 100) if total_questions > 0 else 0
        rank_emoji = get_rank_emoji(i + 1)
        name = p.first_name[:15]
        lines.append(
            f"{rank_emoji} <b>{name}</b> — {p.score:.1f}pts | "
            f"✅{p.correct} ❌{p.wrong} ⏭{p.missed} | {pct:.0f}%"
        )
    return "\n".join(lines)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def truncate(text: str, max_len: int = 100) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def is_group_admin(member_status: str) -> bool:
    return member_status in ("administrator", "creator")
