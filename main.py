from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
import os
import json
from datetime import datetime
import bcrypt
import jwt
import heapq
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from groq import Groq
from dotenv import load_dotenv

import database
import models
import schemas

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing. Add SECRET_KEY to your .env file.")

app = FastAPI(title="Healthcare MVP")

def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "dummy_key" or api_key == "your_actual_api_key_here":
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        print("Groq Client Init Error:", e)
        return None

# Create database tables
models.database.Base.metadata.create_all(bind=database.engine)

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure prescriptions dir exists
os.makedirs("prescriptions", exist_ok=True)

# Security
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(database.get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub_str = payload.get("sub")
        if sub_str is None:
            raise HTTPException(status_code=401, detail="Invalid auth token")
        user_id = int(sub_str)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid auth token")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ------ UI Routes ------
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/appointment/{appt_id}", response_class=HTMLResponse)
def appointment_room(request: Request, appt_id: int):
    return templates.TemplateResponse(request=request, name="appointment.html", context={"appt_id": appt_id})

# ------ API Routes ------
@app.post("/api/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = models.User(name=user.name, email=user.email, password_hash=hashed_password, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/login")
def login(user: schemas.UserLogin, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    
    token = jwt.encode({"sub": str(db_user.id)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "role": db_user.role, "name": db_user.name, "id": db_user.id}

@app.get("/api/users/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.get("/api/doctors", response_model=List[schemas.UserOut])
def get_doctors(db: Session = Depends(database.get_db)):
    return db.query(models.User).filter(models.User.role == "doctor").all()

@app.get("/api/doctors/suggest", response_model=List[schemas.UserOut])
def suggest_doctors(symptoms: str, db: Session = Depends(database.get_db)):
    all_docs = db.query(models.User).filter(models.User.role == "doctor").all()
    if not symptoms:
        return all_docs
    
    s_lower = symptoms.lower()
    
    # Priority mapping
    mapping = {
        "cardiologist": ["chest pain", "heart", "breath", "palpitation"],
        "neurologist": ["headache", "brain", "numbness", "dizziness", "nerve"],
        "orthopedic": ["bone", "joint", "fracture", "muscle", "back pain", "knee"],
        "dermatologist": ["skin", "rash", "itch", "acne", "hair"],
        "gynecologist": ["pregnancy", "period", "women", "menstrual"],
        "urologist": ["kidney", "urine", "bladder", "prostate"],
        "pediatrician": ["child", "baby", "kid", "infant"],
        "ent specialist": ["ear", "nose", "throat", "swallow", "hearing"],
        "psychiatrist": ["depression", "anxiety", "mental", "stress", "sleep"],
        "general physician": ["fever", "cold", "cough", "flu", "weakness"]
    }

    # Assign scores
    scored_docs = []
    for doc in all_docs:
        score = 0
        if doc.specialization:
            spec_lower = doc.specialization.lower()
            keywords = mapping.get(spec_lower, [])
            for k in keywords:
                if k in s_lower:
                    score += 10
        # Give general physician a slight boost if nothing matches perfectly
        if score == 0 and doc.specialization and "general physician" in doc.specialization.lower():
            score = 1
            
        scored_docs.append((score, doc))
        
    # Sort by score descending
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    return [doc for score, doc in scored_docs]

@app.post("/api/appointments", response_model=schemas.AppointmentOut)
def create_appointment(appt: schemas.AppointmentCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can book appointments")
    
    new_appt = models.Appointment(
        patient_id=current_user.id,
        doctor_id=appt.doctor_id,
        date_time=appt.date_time,
        symptoms=appt.symptoms,
        status="pending",
        meeting_link=f"health_mvp_consult_{current_user.id}_{appt.doctor_id}_{int(datetime.now().timestamp())}"
    )
    db.add(new_appt)
    db.commit()
    db.refresh(new_appt)
    return new_appt

def calculate_priority(symptoms: str) -> int:
    if not symptoms: return 0
    s_lower = symptoms.lower()
    if any(k in s_lower for k in ["chest pain", "breathing", "heart", "emergency", "severe"]):
        return 10
    if any(k in s_lower for k in ["fever", "pain", "bleeding", "high"]):
        return 5
    return 2

@app.get("/api/appointments", response_model=List[schemas.AppointmentOut])
def get_appointments(current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role == "doctor":
        appts = db.query(models.Appointment).filter(models.Appointment.doctor_id == current_user.id).all()
        heap = []
        for i, appt in enumerate(appts):
            priority = calculate_priority(appt.symptoms)
            heapq.heappush(heap, (-priority, i, appt))
        
        sorted_appts = []
        while heap:
            _, _, appt = heapq.heappop(heap)
            sorted_appts.append(appt)
        return sorted_appts
    else:
        appts = db.query(models.Appointment).filter(models.Appointment.patient_id == current_user.id).all()
    return appts

@app.put("/api/appointments/{appt_id}/status", response_model=schemas.AppointmentOut)
def update_appointment_status(appt_id: int, status_update: schemas.AppointmentStatusUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can update status")
    
    appt = db.query(models.Appointment).filter(models.Appointment.id == appt_id, models.Appointment.doctor_id == current_user.id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appt.status = status_update.status
    db.commit()
    db.refresh(appt)
    return appt

@app.post("/api/appointments/{appt_id}/prescription", response_model=schemas.PrescriptionOut)
def create_prescription(appt_id: int, p_data: schemas.PrescriptionCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can write prescriptions")
    
    appt = db.query(models.Appointment).filter(models.Appointment.id == appt_id, models.Appointment.doctor_id == current_user.id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Generate PDF with reportlab
    try:
        pdf_filename = f"prescription_{appt_id}.pdf"
        pdf_path = os.path.join("prescriptions", pdf_filename)
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "Medicare - Digital Prescription")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        c.drawString(50, height - 100, f"Doctor: {current_user.name}")
        c.drawString(50, height - 120, f"Patient Name: {(appt.patient.name if appt.patient else str(appt.patient_id))}")
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
        y = draw_text_block("Symptoms", p_data.symptoms, y)
        y = draw_text_block("Diagnosis", p_data.diagnosis, y)
        y = draw_text_block("Medicines", p_data.medicines, y)
        y = draw_text_block("Advice & Precautions", p_data.advice, y)
        if p_data.follow_up:
            y = draw_text_block("Follow up", p_data.follow_up, y)
        
        c.save()
    except Exception as e:
        print(f"CRITICAL ERROR generating PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF Generation failed: {e}")

    # Save to DB
    prescription = db.query(models.Prescription).filter(models.Prescription.appointment_id == appt_id).first()
    if prescription:
        prescription.symptoms = p_data.symptoms
        prescription.diagnosis = p_data.diagnosis
        prescription.medicines = p_data.medicines
        prescription.advice = p_data.advice
        prescription.follow_up = p_data.follow_up
        prescription.file_path = pdf_path
    else:
        prescription = models.Prescription(
            appointment_id=appt_id,
            symptoms=p_data.symptoms,
            diagnosis=p_data.diagnosis,
            medicines=p_data.medicines,
            advice=p_data.advice,
            follow_up=p_data.follow_up,
            file_path=pdf_path
        )
        db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription

@app.get("/api/appointments/{appt_id}/prescription", response_model=schemas.PrescriptionOut)
def get_prescription(appt_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    appt = db.query(models.Appointment).filter(models.Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role == "patient" and appt.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if current_user.role == "doctor" and appt.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if not appt.prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    
    return appt.prescription

@app.get("/api/prescriptions/{appt_id}/download")
def download_prescription_pdf(appt_id: int, db: Session = Depends(database.get_db)):
    # Note: To download simply, for MVP we might allow direct access or require token via query param
    # We will make it open via link if user has URL for MVP simplicity, or just check DB.
    prescription = db.query(models.Prescription).filter(models.Prescription.appointment_id == appt_id).first()
    if not prescription or not prescription.file_path:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    return FileResponse(prescription.file_path, media_type="application/pdf", filename=f"prescription_{appt_id}.pdf", headers={"Content-Disposition": f"attachment; filename=prescription_{appt_id}.pdf"})

@app.get("/api/test-ai")
def test_ai():
    client = get_groq_client()
    if not client:
        return {"status": "error", "message": "GROQ_API_KEY is missing or invalid in .env file."}
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Hello. Just say 'API works!'"}],
            temperature=0.3
        )
        return {"status": "success", "response": completion.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": f"Groq API Error: {str(e)}"}

# ------ Translation API ------
@app.post("/api/translate", response_model=schemas.TranslateResponse)
def translate_text(req: schemas.TranslateRequest):
    """Translate text between languages. Uses deep-translator (free, no API key needed)."""
    if not req.text or not req.text.strip():
        return schemas.TranslateResponse(
            original_text=req.text or "",
            translated_text=req.text or "",
            detected_lang=req.source_lang,
            target_lang=req.target_lang,
            success=False
        )
    
    try:
        from deep_translator import GoogleTranslator
        
        source = req.source_lang if req.source_lang != "auto" else "auto"
        translator = GoogleTranslator(source=source, target=req.target_lang)
        translated = translator.translate(req.text.strip())
        
        # deep-translator doesn't return detected language directly when source='auto'
        # We'll report 'auto' as detected in that case
        detected = req.source_lang
        if req.source_lang == "auto":
            try:
                from deep_translator import single_detection
                detected = single_detection(req.text.strip(), api_key=None)
            except Exception:
                detected = "auto"
        
        return schemas.TranslateResponse(
            original_text=req.text,
            translated_text=translated or req.text,
            detected_lang=detected,
            target_lang=req.target_lang,
            success=True
        )
    except Exception as e:
        print(f"Translation Error: {e}")
        # Graceful fallback: return original text, never crash
        return schemas.TranslateResponse(
            original_text=req.text,
            translated_text=req.text,
            detected_lang=req.source_lang,
            target_lang=req.target_lang,
            success=False
        )

@app.post("/api/ai/generate-prescription", response_model=schemas.AIPredictResponse)
def generate_ai_prescription(request: schemas.AIPredictRequest, current_user: models.User = Depends(get_current_user)):
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can use AI assistant")
    
    client = get_groq_client()
    if not client:
        return schemas.AIPredictResponse(
            diagnosis="[No API Key provided] Simulated Diagnosis based on: " + request.symptoms,
            medicines="Paracetamol 500mg\nSimulated Medicine",
            advice="Please configure GROQ_API_KEY in .env file to get real AI responses."
        )
    
    prompt = f"Given the following symptoms: {request.symptoms} and patient history: {request.history or 'None'}, suggest:\n1. Diagnosis\n2. Medicines\n3. Dosage\n4. Precautions\nKeep response structured and concise returning a JSON object with keys: 'diagnosis', 'medicines' (including dosage), 'advice' (for precautions)."

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful medical assistant. Always return exact JSON structure: {\"diagnosis\": \"...\", \"medicines\": \"...\", \"advice\": \"...\"}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        
        def dict_to_str(val):
            if isinstance(val, dict):
                return "\n".join(f"{k}: {v}" for k, v in val.items())
            if isinstance(val, list):
                return "\n".join(str(v) for v in val)
            return str(val)

        return schemas.AIPredictResponse(
            diagnosis=dict_to_str(data.get("diagnosis", "Unknown")),
            medicines=dict_to_str(data.get("medicines", "Unknown")),
            advice=dict_to_str(data.get("advice", "Unknown"))
        )
    except Exception as e:
        print("Groq API Call Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
