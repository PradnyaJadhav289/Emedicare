from pydantic import BaseModel
from typing import Optional, List

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    specialization: Optional[str] = None
    experience: Optional[int] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True

class AppointmentCreate(BaseModel):
    doctor_id: int
    date_time: str
    symptoms: Optional[str] = None

class AppointmentStatusUpdate(BaseModel):
    status: str

class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    date_time: str
    status: str
    meeting_link: Optional[str] = None
    symptoms: Optional[str] = None
    patient: UserOut
    doctor: UserOut

    class Config:
        from_attributes = True

class PrescriptionCreate(BaseModel):
    symptoms: str
    diagnosis: str
    medicines: str
    advice: str
    follow_up: Optional[str] = None

class PrescriptionOut(BaseModel):
    id: int
    appointment_id: int
    symptoms: str
    diagnosis: str
    medicines: str
    advice: str
    follow_up: Optional[str] = None
    file_path: Optional[str] = None

    class Config:
        from_attributes = True

class AIPredictRequest(BaseModel):
    symptoms: str
    history: Optional[str] = None

class AIPredictResponse(BaseModel):
    diagnosis: str
    medicines: str
    advice: str

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "en"

class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_lang: str
    target_lang: str
    success: bool
