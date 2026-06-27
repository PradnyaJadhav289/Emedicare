from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from datetime import datetime

pdf_path = "test_prescription.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)
width, height = letter
c.setFont("Helvetica-Bold", 16)
c.drawString(50, height - 50, "Medicare - Digital Prescription")
c.setFont("Helvetica", 12)
c.drawString(50, height - 80, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
c.drawString(50, height - 100, f"Doctor: Test Doctor")
c.drawString(50, height - 120, f"Patient Name: Test Patient")
c.line(50, height - 130, width - 50, height - 130)

def draw_text_block(title, content, y_pos):
    if not content:
        content = "None provided"
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos, title + ":")
    y_pos -= 15
    c.setFont("Helvetica", 11)
    lines = simpleSplit(str(content), "Helvetica", 11, width - 100)
    for line in lines:
        c.drawString(50, y_pos, line)
        y_pos -= 15
    return y_pos - 10

y = height - 150
y = draw_text_block("Symptoms", "Fever", y)
y = draw_text_block("Diagnosis", "Viral Fever", y)
y = draw_text_block("Medicines", "Paracetamol", y)
y = draw_text_block("Advice & Precautions", "Rest", y)
y = draw_text_block("Follow up", "3 days", y)

c.save()
print("Success")
