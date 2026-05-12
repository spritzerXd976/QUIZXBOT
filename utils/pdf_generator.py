import io
from datetime import datetime
from typing import List
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from models import QuizSession, Quiz


def generate_result_pdf(session: QuizSession, quiz: Quiz, user_id: int) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=22, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=12, spaceAfter=4, textColor=colors.HexColor("#16213e"),
        alignment=TA_CENTER,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontSize=13, spaceAfter=6, textColor=colors.HexColor("#0f3460"),
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, spaceAfter=4, textColor=colors.HexColor("#333333"),
    )
    correct_style = ParagraphStyle(
        "Correct", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#2d6a4f"),
    )
    wrong_style = ParagraphStyle(
        "Wrong", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#d62828"),
    )

    story = []
    participant = session.participants.get(user_id)
    if not participant:
        story.append(Paragraph("No data found for this user.", body_style))
        doc.build(story)
        return buffer.getvalue()

    total_q = session.total_questions
    percentage = (participant.correct / total_q * 100) if total_q > 0 else 0
    max_score = quiz.settings.get("correct_score", 4) * total_q

    # Header
    story.append(Paragraph("📊 Quiz Result Report", title_style))
    story.append(Paragraph(quiz.title, subtitle_style))
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0f3460")))
    story.append(Spacer(1, 4 * mm))

    # Participant Info
    story.append(Paragraph("👤 Participant Details", section_style))
    info_data = [
        ["Name", participant.first_name + (f" (@{participant.username})" if participant.username else "")],
        ["Quiz", quiz.title],
        ["Date", session.started_at.strftime("%d %B %Y, %H:%M UTC")],
        ["Total Questions", str(total_q)],
    ]
    info_table = Table(info_data, colWidths=[50 * mm, 120 * mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f4f8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # Score Summary
    story.append(Paragraph("📈 Score Summary", section_style))
    score_data = [
        ["Metric", "Value"],
        ["✅ Correct Answers", f"{participant.correct} / {total_q}"],
        ["❌ Wrong Answers", f"{participant.wrong}"],
        ["⏭ Missed / Skipped", f"{participant.missed}"],
        ["🎯 Score", f"{participant.score:.1f} / {max_score:.1f}"],
        ["📊 Percentage", f"{percentage:.1f}%"],
        ["⏱ Time Taken", f"{participant.time_taken:.1f} seconds"],
        ["🏅 Grade", _get_grade(percentage)],
    ]
    score_table = Table(score_data, colWidths=[80 * mm, 90 * mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f8ff")]),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 6 * mm))

    # Leaderboard position
    sorted_participants = session.get_sorted_participants()
    rank = next((i + 1 for i, p in enumerate(sorted_participants) if p.user_id == user_id), None)
    if rank:
        story.append(Paragraph(f"🏆 Your Rank: #{rank} out of {len(sorted_participants)} participants", section_style))
        story.append(Spacer(1, 4 * mm))

    # Detailed Question Analysis
    story.append(Paragraph("🔍 Question-wise Analysis", section_style))
    story.append(Spacer(1, 2 * mm))

    questions_map = {q.question_id: q for q in quiz.questions}
    for i, answer in enumerate(participant.answers):
        q = questions_map.get(answer.get("question_id"))
        if not q:
            continue

        q_num = i + 1
        is_missed = answer.get("missed", False)
        is_correct = answer.get("is_correct", False)

        if is_missed:
            status = "⏭ MISSED"
            status_color = colors.HexColor("#888888")
        elif is_correct:
            status = "✅ CORRECT"
            status_color = colors.HexColor("#2d6a4f")
        else:
            status = "❌ WRONG"
            status_color = colors.HexColor("#d62828")

        q_text = f"Q{q_num}. {q.text}"
        story.append(Paragraph(q_text, body_style))

        options_lines = []
        labels = ["A", "B", "C", "D"]
        for j, opt in enumerate(q.options):
            prefix = ""
            if j == answer.get("correct") or opt.is_correct:
                prefix = "✓ "
            elif j == answer.get("selected") and not is_correct:
                prefix = "✗ "
            options_lines.append(f"  {labels[j]}. {prefix}{opt.text}")

        for line in options_lines:
            style = correct_style if "✓" in line else (wrong_style if "✗" in line else body_style)
            story.append(Paragraph(line, style))

        status_para = ParagraphStyle("Status", parent=styles["Normal"], fontSize=9, textColor=status_color)
        time_str = f" | Time: {answer.get('time_taken', 0):.1f}s" if not is_missed else ""
        story.append(Paragraph(f"Result: {status}{time_str}", status_para))

        if q.explanation:
            exp_style = ParagraphStyle("Exp", parent=styles["Italic"], fontSize=9, textColor=colors.HexColor("#555555"))
            story.append(Paragraph(f"💡 {q.explanation}", exp_style))

        story.append(Spacer(1, 3 * mm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                                  textColor=colors.gray, alignment=TA_CENTER)
    story.append(Paragraph(f"Generated on {datetime.utcnow().strftime('%d %B %Y %H:%M UTC')} | Quiz Bot", footer_style))

    doc.build(story)
    return buffer.getvalue()


def generate_full_leaderboard_pdf(session: QuizSession, quiz: Quiz) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, alignment=TA_CENTER,
                                  textColor=colors.HexColor("#1a1a2e"))
    story.append(Paragraph(f"🏆 Leaderboard — {quiz.title}", title_style))
    story.append(Spacer(1, 6*mm))

    sorted_p = session.get_sorted_participants()
    total_q = session.total_questions
    max_score = quiz.settings.get("correct_score", 4) * total_q

    table_data = [["Rank", "Name", "Score", "Correct", "Wrong", "Missed", "%", "Time"]]
    for i, p in enumerate(sorted_p):
        pct = (p.correct / total_q * 100) if total_q > 0 else 0
        table_data.append([
            f"#{i+1}",
            p.first_name[:20],
            f"{p.score:.1f}",
            str(p.correct),
            str(p.wrong),
            str(p.missed),
            f"{pct:.1f}%",
            f"{p.time_taken:.1f}s",
        ])

    t = Table(table_data, colWidths=[15*mm, 45*mm, 20*mm, 18*mm, 18*mm, 18*mm, 18*mm, 18*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f8ff")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    doc.build(story)
    return buffer.getvalue()


def _get_grade(percentage: float) -> str:
    if percentage >= 90:
        return "A+ (Excellent)"
    elif percentage >= 80:
        return "A (Very Good)"
    elif percentage >= 70:
        return "B (Good)"
    elif percentage >= 60:
        return "C (Average)"
    elif percentage >= 50:
        return "D (Pass)"
    else:
        return "F (Fail)"
