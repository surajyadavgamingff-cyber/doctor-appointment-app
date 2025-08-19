from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Date, Time
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional

# ---------------- Config ----------------
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

DATABASE_URL = "sqlite:///./appointments.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------- Database Setup ----------------
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)  # 'doctor' or 'patient'
    specialty = Column(String, nullable=True)
    fees = Column(Integer, nullable=True)

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=True)
    status = Column(String, default="pending")
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"))

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])


Base.metadata.create_all(bind=engine)

# ---------------- Auth Helpers ----------------
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# ---------------- Schemas ----------------


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str
    specialty: Optional[str] = None
    fees: Optional[int] = None


class UserLogin(BaseModel):
    email: str
    password: str

class AppointmentCreate(BaseModel):
    doctor_id: int
    date: str

class AppointmentUpdate(BaseModel):
    status: str
    time: str = None

# ---------------- App Init ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Routes ----------------
@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.role == "doctor":
        existing_doctor = db.query(User).filter(User.role == "doctor").first()
        if existing_doctor:
            raise HTTPException(status_code=400, detail="Only one doctor allowed")
        if user.name.strip().lower() != "suraj":
            raise HTTPException(status_code=400, detail="Only doctor named 'Suraj' is allowed")

    hashed_pw = get_password_hash(user.password)
    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_pw,
        role=user.role,
        specialty=user.specialty,
        fees=user.fees
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully"}

@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": db_user.email, "role": db_user.role})
    return {"access_token": token, "token_type": "bearer", "role": db_user.role, "id": db_user.id}

@app.get("/doctors")
def get_doctors(db: Session = Depends(get_db)):
    doctors = db.query(User).filter(User.role == "doctor").all()
    return doctors

@app.post("/appointments")
def book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can book appointments")

    try:
        appointment_date = datetime.strptime(data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    new_appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=data.doctor_id,
        date=appointment_date,
        status="pending"
    )
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)
    return {"message": "Appointment booked!"}

@app.get("/appointments")
def get_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = []
    if current_user.role == "patient":
        appts = db.query(Appointment).filter(Appointment.patient_id == current_user.id).all()
        for appt in appts:
            result.append({
                "id": appt.id,
                "doctor_id": appt.doctor_id,
                "doctor_name": appt.doctor.name,
                "date": appt.date.isoformat(),
                "status": appt.status,
                "time": appt.time.strftime("%H:%M:%S") if appt.time else None
            })
    elif current_user.role == "doctor":
        appts = db.query(Appointment).filter(Appointment.doctor_id == current_user.id).all()
        for appt in appts:
            result.append({
                "id": appt.id,
                "patient_id": appt.patient_id,
                "patient_name": appt.patient.name,
                "date": appt.date.isoformat(),
                "status": appt.status,
                "time": appt.time.strftime("%H:%M:%S") if appt.time else None
            })
    return result

@app.put("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: int, 
    appointment_update: AppointmentUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can update status")

    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.doctor_id == current_user.id
    ).first()

    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt.status = appointment_update.status

    if appointment_update.time:
        try:
            # Try parsing with seconds first
            try:
                appt.time = datetime.strptime(appointment_update.time, "%H:%M:%S").time()
            except ValueError:
                # If no seconds, parse HH:MM and add 0 seconds
                appt.time = datetime.strptime(appointment_update.time, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM or HH:MM:SS")

    db.commit()
    db.refresh(appt)
    return {"message": "Appointment updated"}


# ---------------- Auto-create Doctor Suraj ----------------
def init_doctor_suraj():
    db = SessionLocal()
    existing = db.query(User).filter(User.role == "doctor", User.name == "Suraj").first()
    if not existing:
        suraj = User(
            name="Suraj",
            email="suraj@example.com",
            password=get_password_hash("password123"),
            role="doctor",
            specialty="General Physician",
            fees=500
        )
        db.add(suraj)
        db.commit()
    db.close()

init_doctor_suraj()
