from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import datetime

def generate_results_pdf(leaders, quiz_id, filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "Quiz Results")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Quiz ID: {quiz_id}")
    c.drawString(50, height - 100, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    c.drawString(50, height - 140, "Rank | Name | Score | Correct | Wrong")
    c.line(50, height - 145, width - 50, height - 145)

    y = height - 170
    for i, p in enumerate(leaders, 1):
        text = f"{i} | {p['name']} | {p['score']} | {p['correct']} | {p['wrong']}"
        c.drawString(50, y, text)
        y -= 20

        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = height - 50

    c.save()
