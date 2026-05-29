# main.py (ЧАСТЬ 1/2) - Веб-приложение Pool CRM

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func
from threading import Thread
from typing import Optional, List
from datetime import datetime, date, timedelta
import random
import string
import os
from fastapi import UploadFile, File
import shutil
from PIL import Image
import hashlib
from pydantic import BaseModel, Field

from database import (
    engine, Base, SessionLocal, get_db,
    ParentDB, ChildDB, CoachDB, GroupDB, TimeSlotDB,
    EnrollmentDB, ApplicationDB, TrainingDB, AttendanceDB,
    TransferRequestDB, TransferHistoryDB, NotificationDB,
    UserRole, EnrollmentStatus, TrainingStatus, AttendanceStatus,
    ApplicationStatus, GalleryImageDB
)

from vk_bot import start_vk_worker, stop_vk_worker


# ========== PYDANTIC МОДЕЛИ ДЛЯ ВАЛИДАЦИИ ==========

# ---- Дети ----
class ChildCreate(BaseModel):
    """Модель для создания/обновления ребёнка"""
    name: str = Field(..., min_length=1, max_length=100, description="ФИО ребёнка")
    birthdate: date = Field(..., description="Дата рождения")
    class_num: Optional[int] = Field(None, ge=0, le=11, description="Класс (0-11)")
    study_year: Optional[int] = Field(None, ge=1, le=4, description="Год обучения (1-4)")
    medical_note: Optional[str] = Field(None, max_length=500, description="Медицинские показания")

class ChildResponse(BaseModel):
    """Ответ с данными ребёнка"""
    id: int
    name: str
    birthdate: date
    class_num: Optional[int] = None
    study_year: Optional[int] = None
    medical_note: Optional[str] = None
    parent_id: int
    is_active: bool
    group_name: Optional[str] = None
    
    class Config:
        from_attributes = True

# ---- Группы ----
class GroupCreate(BaseModel):
    """Модель для создания/обновления группы"""
    name: str = Field(..., min_length=1, max_length=100, description="Название группы")
    level: int = Field(..., ge=0, le=5, description="Уровень группы (0-5)")
    coach_id: Optional[int] = Field(None, description="ID тренера")
    max_capacity: int = Field(12, ge=1, le=30, description="Максимальное количество детей")

class GroupResponse(BaseModel):
    """Ответ с данными группы"""
    id: int
    name: str
    level: int
    coach_id: Optional[int] = None
    coach_name: Optional[str] = None
    max_capacity: int
    current_enrollment: int
    is_active: bool
    
    class Config:
        from_attributes = True

# ---- Тренеры ----
class CoachCreate(BaseModel):
    """Модель для создания/обновления тренера"""
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone: Optional[str] = Field(None, pattern=r'^[\d\s\+-]{10,20}$')
    password: str = Field(..., min_length=4)

class CoachResponse(BaseModel):
    """Ответ с данными тренера"""
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    groups_count: int = 0
    
    class Config:
        from_attributes = True

# ---- Посещаемость ----
class AttendanceUpdate(BaseModel):
    """Модель для отметки посещаемости"""
    training_id: int = Field(..., gt=0)
    child_id: int = Field(..., gt=0)
    status: str = Field(..., pattern=r'^(present|absent_sick|absent_family|absent_no_reason)$')

class AttendanceResponse(BaseModel):
    """Ответ с данными посещаемости"""
    child_id: int
    child_name: str
    status: str
    marked_at: Optional[str] = None

# ---- Заявки ----
class ApplicationCreate(BaseModel):
    """Модель для создания заявки"""
    group_id: int = Field(..., gt=0)
    parent_name: str = Field(..., min_length=1)
    parent_phone: str = Field(..., min_length=10)
    parent_email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    child_name: str = Field(..., min_length=1)
    child_birthdate: date
    child_class: Optional[int] = None
    child_study_year: Optional[int] = None
    medical_cert_date: Optional[date] = None
    medical_note: Optional[str] = None

class ApplicationResponse(BaseModel):
    """Ответ с данными заявки"""
    id: int
    child_name: Optional[str] = None
    group_name: str
    status: str
    created_at: str
    public_child_name: Optional[str] = None
    
    class Config:
        from_attributes = True

# ---- Авторизация ----
class LoginRequest(BaseModel):
    """Модель для входа"""
    email: str
    password: str

class UserResponse(BaseModel):
    """Ответ с данными пользователя"""
    id: int
    role: str
    name: str
    email: str


# ========== НАСТРОЙКА ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск приложения...")
    Base.metadata.create_all(bind=engine)
    try:
        start_vk_worker(None)
        print("🤖 VK бот запущен")
    except Exception as e:
        print(f"⚠️ Ошибка запуска VK бота: {e}")
        import traceback
        traceback.print_exc()
    print("✅ Приложение готово!")
    yield


app = FastAPI(title="Pool CRM", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")
sessions = {}


# ========== ФУНКЦИИ ПРОВЕРКИ ПРАВ ==========

def get_current_user(request: Request, db: Session):
    """Получение текущего пользователя из сессии"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None

    user_data = sessions[session_id]

    if user_data["role"] == "admin":
        return {
            "id": user_data["id"],
            "name": user_data["name"],
            "email": user_data["email"],
            "role": "admin"
        }

    if user_data["role"] == "parent":
        user = db.query(ParentDB).filter(ParentDB.id == user_data["id"], ParentDB.is_active == True).first()
        if user:
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": "parent",
                "phone": user.phone,
                "is_vk_linked": user.is_vk_linked,
                "vk_id": user.vk_id,
                "notify_absences": user.notify_absences,
                "notify_reminders": user.notify_reminders
            }

    if user_data["role"] == "coach":
        user = db.query(CoachDB).filter(CoachDB.id == user_data["id"]).first()
        if user:
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": "coach",
                "phone": user.phone
            }

    return None


def get_user_object(request: Request, db: Session):
    """Получение объекта пользователя из БД"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None

    user_data = sessions[session_id]

    if user_data["role"] == "admin":
        return None
    if user_data["role"] == "parent":
        return db.query(ParentDB).filter(ParentDB.id == user_data["id"]).first()
    if user_data["role"] == "coach":
        return db.query(CoachDB).filter(CoachDB.id == user_data["id"]).first()
    return None


def calculate_age(birthdate: date) -> float:
    """Вычисление возраста в годах"""
    today = date.today()
    age = today.year - birthdate.year
    if today.month < birthdate.month or (today.month == birthdate.month and today.day < birthdate.day):
        age -= 1
    return age


def get_group_enrollment_count(group_id: int, db: Session) -> int:
    """Получение актуального количества детей в группе"""
    return db.query(EnrollmentDB).filter(
        EnrollmentDB.group_id == group_id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).count()


def check_parent_access(child_id: int, parent_id: int, db: Session) -> bool:
    """Проверяет, принадлежит ли ребёнок родителю"""
    child = db.query(ChildDB).filter(
        ChildDB.id == child_id,
        ChildDB.parent_id == parent_id,
        ChildDB.is_active == True
    ).first()
    if not child:
        raise HTTPException(status_code=403, detail="Access denied: child does not belong to this parent")
    return True


def check_coach_access(group_id: int, coach_id: int, db: Session) -> bool:
    """Проверяет, принадлежит ли группа тренеру"""
    group = db.query(GroupDB).filter(
        GroupDB.id == group_id,
        GroupDB.coach_id == coach_id,
        GroupDB.is_active == True
    ).first()
    if not group:
        raise HTTPException(status_code=403, detail="Access denied: group does not belong to this coach")
    return True


def check_admin_access(user_role: str) -> bool:
    """Проверяет, является ли пользователь администратором"""
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Access denied: admin access required")
    return True


def get_child_or_404(child_id: int, db: Session) -> ChildDB:
    """Получает ребёнка по ID или возвращает 404"""
    child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


def get_group_or_404(group_id: int, db: Session) -> GroupDB:
    """Получает группу по ID или возвращает 404"""
    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def get_coach_or_404(coach_id: int, db: Session) -> CoachDB:
    """Получает тренера по ID или возвращает 404"""
    coach = db.query(CoachDB).filter(CoachDB.id == coach_id).first()
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found")
    return coach


def get_training_or_404(training_id: int, db: Session) -> TrainingDB:
    """Получает тренировку по ID или возвращает 404"""
    training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return training


# ========== АУТЕНТИФИКАЦИЯ ==========
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(name="index.html", request=request, context={"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, message: str = None, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(name="login.html", request=request, context={"request": request, "error": error, "message": message})


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if email == "admin@pool.ru" and password == "admin123":
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sessions[session_id] = {"id": 1, "role": "admin", "name": "Администратор", "email": email}
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    parent = db.query(ParentDB).filter(ParentDB.email == email, ParentDB.password == password, ParentDB.is_active == True).first()
    if parent:
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sessions[session_id] = {"id": parent.id, "role": "parent", "name": parent.name, "email": parent.email}
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    coach = db.query(CoachDB).filter(CoachDB.email == email, CoachDB.password == password, CoachDB.is_active == True).first()
    if coach:
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sessions[session_id] = {"id": coach.id, "role": "coach", "name": coach.name, "email": coach.email}
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    return await login_page(request, error="Неверный email или пароль")


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_id")
    return response


# ========== РЕГИСТРАЦИЯ (ЗАЯВКА ОТ РОДИТЕЛЯ) ==========
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, child_birthdate: str = None, child_study_year: str = None, group_id: str = None, db: Session = Depends(get_db)):
    groups = db.query(GroupDB).filter(GroupDB.is_active == True).all()
    groups_data = []
    for group in groups:
        current_enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == group.id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).count()
        groups_data.append({
            "id": group.id, "name": group.name, "level": group.level,
            "max_capacity": group.max_capacity, "current_enrollment": current_enrollment,
            "has_free_places": current_enrollment < group.max_capacity
        })
    selected_group_id = int(group_id) if group_id else None
    return templates.TemplateResponse(name="register.html", request=request, context={"request": request, "groups": groups_data, "selected_group_id": selected_group_id, "form_data": {}})


@app.post("/register")
async def register(request: Request, parent_name: str = Form(...), parent_phone: str = Form(...), parent_email: str = Form(...), child_name: str = Form(...), child_birthdate: str = Form(...), child_class: int = Form(None), child_study_year: int = Form(None), has_medical_cert: Optional[bool] = Form(False), medical_cert_date: Optional[str] = Form(None), medical_note: Optional[str] = Form(None), group_id: int = Form(...), db: Session = Depends(get_db)):
    group = db.query(GroupDB).filter(GroupDB.id == group_id, GroupDB.is_active == True).first()
    if not group:
        return await register_page(request, error="Группа не найдена")
    
    current_enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == group_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).count()
    status = ApplicationStatus.WAITING_LIST if current_enrollment >= group.max_capacity else ApplicationStatus.NEW
    
    application = ApplicationDB(
        group_id=group_id, status=status,
        public_parent_name=parent_name, public_parent_phone=parent_phone, public_parent_email=parent_email,
        public_child_name=child_name, public_child_birthdate=datetime.strptime(child_birthdate, "%Y-%m-%d").date() if child_birthdate else None,
        public_child_class=child_class, public_child_study_year=child_study_year,
        public_child_medical_date=datetime.strptime(medical_cert_date, "%Y-%m-%d").date() if medical_cert_date and has_medical_cert else None,
        public_child_medical_note=medical_note
    )
    db.add(application)
    db.commit()
    
    return templates.TemplateResponse(name="login.html", request=request, context={"request": request, "message": "Заявка успешно отправлена! После рассмотрения администратором вы получите доступ к системе."})


# ========== ДАШБОРД ==========
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    
    children_count = db.query(ChildDB).filter(ChildDB.is_active == True).count()
    groups_count = db.query(GroupDB).filter(GroupDB.is_active == True).count()
    coaches_count = db.query(CoachDB).filter(CoachDB.is_active == True).count()
    today = date.today()
    trainings_this_month = db.query(TrainingDB).filter(TrainingDB.date >= date(today.year, today.month, 1), TrainingDB.date <= date(today.year, today.month, 28)).count()
    attendances = db.query(AttendanceDB).filter(AttendanceDB.status == AttendanceStatus.PRESENT).count()
    total_attendances = db.query(AttendanceDB).count()
    attendance_rate = round((attendances / total_attendances * 100) if total_attendances > 0 else 0)
    pending_applications = db.query(ApplicationDB).filter(ApplicationDB.status.in_([ApplicationStatus.NEW, ApplicationStatus.ON_REVIEW])).count()
    
    stats = {"children": children_count, "groups": groups_count, "coaches": coaches_count, "trainings_this_month": trainings_this_month, "attendance_rate": attendance_rate, "pending_applications": pending_applications}
    
    user_children = []
    if user["role"] == "parent":
        children = db.query(ChildDB).filter(ChildDB.parent_id == user["id"], ChildDB.is_active == True).all()
        for child in children:
            enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.child_id == child.id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).first()
            user_children.append({"id": child.id, "name": child.name, "birthdate": child.birthdate, "class_num": child.class_num, "group_name": enrollment.group.name if enrollment else None, "is_active": child.is_active})
    user["children"] = user_children
    
    return templates.TemplateResponse(name="dashboard.html", request=request, context={"request": request, "user": user, "stats": stats})


# ========== ДЕТИ (ВЕБ) ==========
@app.get("/children", response_class=HTMLResponse)
async def children_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    query = db.query(ChildDB).filter(ChildDB.is_active == True)
    if user["role"] == "parent":
        query = query.filter(ChildDB.parent_id == user["id"])
    children = query.all()
    children_data = []
    for child in children:
        enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.child_id == child.id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).first()
        children_data.append({"id": child.id, "name": child.name, "birthdate": child.birthdate, "class_num": child.class_num, "study_year": child.study_year, "group_name": enrollment.group.name if enrollment else None, "is_active": child.is_active})
    return templates.TemplateResponse(name="children.html", request=request, context={"request": request, "user": user, "children": children_data})


@app.get("/children/add", response_class=HTMLResponse)
async def add_child_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    groups = db.query(GroupDB).filter(GroupDB.is_active == True).all()
    groups_data = []
    for group in groups:
        current_count = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == group.id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).count()
        groups_data.append({"id": group.id, "name": group.name, "current_enrollment": current_count, "max_capacity": group.max_capacity})
    return templates.TemplateResponse(name="child_form.html", request=request, context={"request": request, "user": user, "title": "Добавить ребёнка", "child": {}, "groups": groups_data})


@app.post("/children/add")
async def add_child(request: Request, name: str = Form(...), birthdate: str = Form(...), class_num: Optional[int] = Form(None), study_year: Optional[int] = Form(None), medical_note: Optional[str] = Form(None), group_id: Optional[int] = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    child = ChildDB(name=name, birthdate=datetime.strptime(birthdate, "%Y-%m-%d").date(), class_num=class_num, study_year=study_year, medical_note=medical_note, parent_id=user["id"])
    db.add(child)
    db.flush()
    if group_id:
        group = db.query(GroupDB).filter(GroupDB.id == group_id, GroupDB.is_active == True).first()
        if group:
            current_count = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == group_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).count()
            if current_count < group.max_capacity:
                enrollment = EnrollmentDB(child_id=child.id, group_id=group_id, status=EnrollmentStatus.ACTIVE, start_date=date.today())
            else:
                enrollment = EnrollmentDB(child_id=child.id, group_id=group_id, status=EnrollmentStatus.WAITING_LIST, start_date=date.today())
            db.add(enrollment)
    db.commit()
    return RedirectResponse(url="/children", status_code=303)


@app.get("/children/{child_id}/edit", response_class=HTMLResponse)
async def edit_child_page(request: Request, child_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    child = db.query(ChildDB).filter(ChildDB.id == child_id, ChildDB.parent_id == user["id"]).first()
    if not child:
        return RedirectResponse(url="/children")
    return templates.TemplateResponse(name="child_form.html", request=request, context={"request": request, "user": user, "title": "Редактировать ребёнка", "child": child})


@app.post("/children/{child_id}/edit")
async def edit_child(request: Request, child_id: int, name: str = Form(...), birthdate: str = Form(...), class_num: Optional[int] = Form(None), study_year: Optional[int] = Form(None), medical_note: Optional[str] = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    child = db.query(ChildDB).filter(ChildDB.id == child_id, ChildDB.parent_id == user["id"]).first()
    if not child:
        return RedirectResponse(url="/children")
    child.name = name
    child.birthdate = datetime.strptime(birthdate, "%Y-%m-%d").date()
    child.class_num = class_num
    child.study_year = study_year
    child.medical_note = medical_note
    db.commit()
    return RedirectResponse(url="/children", status_code=303)


@app.get("/children/{child_id}/delete")
async def delete_child(request: Request, child_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
    if child:
        child.is_active = False
        enrollments = db.query(EnrollmentDB).filter(EnrollmentDB.child_id == child_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).all()
        for enrollment in enrollments:
            enrollment.status = EnrollmentStatus.COMPLETED
            enrollment.end_date = date.today()
        db.commit()
    return RedirectResponse(url="/children", status_code=303)


@app.post("/children/{child_id}/enroll")
async def enroll_child_to_group(request: Request, child_id: int, group_id: int = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] not in ["admin", "coach"]:
        return RedirectResponse(url="/dashboard")
    child = get_child_or_404(child_id, db)
    if not child.is_active:
        return RedirectResponse(url="/children", status_code=303)
    group = get_group_or_404(group_id, db)
    existing = db.query(EnrollmentDB).filter(EnrollmentDB.child_id == child_id, EnrollmentDB.group_id == group_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).first()
    if existing:
        return RedirectResponse(url=f"/children/{child_id}", status_code=303)
    current_count = get_group_enrollment_count(group_id, db)
    if current_count >= group.max_capacity:
        return RedirectResponse(url=f"/children/{child_id}?error=group_full", status_code=303)
    enrollment = EnrollmentDB(child_id=child_id, group_id=group_id, status=EnrollmentStatus.ACTIVE, start_date=date.today())
    db.add(enrollment)
    db.commit()
    return RedirectResponse(url=f"/children/{child_id}", status_code=303)


@app.post("/children/{child_id}/disenroll")
async def disenroll_child_from_group(request: Request, child_id: int, enrollment_id: int = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] not in ["admin", "coach"]:
        return RedirectResponse(url="/dashboard")
    enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.id == enrollment_id, EnrollmentDB.child_id == child_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).first()
    if enrollment:
        enrollment.status = EnrollmentStatus.COMPLETED
        enrollment.end_date = date.today()
        db.commit()
    return RedirectResponse(url=f"/children/{child_id}", status_code=303)


# ========== ГРУППЫ (ВЕБ) ==========
@app.get("/groups", response_class=HTMLResponse)
async def groups_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    
    query = db.query(GroupDB).filter(GroupDB.is_active == True)
    if user["role"] == "coach":
        query = query.filter(GroupDB.coach_id == user["id"])
    
    groups = query.all()
    groups_data = []
    for group in groups:
        current_count = db.query(EnrollmentDB).filter(
            EnrollmentDB.group_id == group.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).count()
        groups_data.append({
            "id": group.id,
            "name": group.name,
            "level": group.level,
            "coach_name": group.coach.name if group.coach else None,
            "max_capacity": group.max_capacity,
            "current_enrollment": current_count,
            "age_range": "6-16"
        })
    
    return templates.TemplateResponse(name="groups.html", request=request, context={"request": request, "user": user, "groups": groups_data})


@app.get("/groups/add", response_class=HTMLResponse)
async def add_group_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()
    return templates.TemplateResponse(name="group_form.html", request=request, context={"request": request, "user": user, "title": "Создать группу", "group": {}, "coaches": coaches})


@app.post("/groups/add")
async def add_group(request: Request, name: str = Form(...), level: int = Form(...), max_capacity: int = Form(12), coach_id: Optional[int] = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    group = GroupDB(name=name, level=level, max_capacity=max_capacity, coach_id=coach_id if coach_id else None)
    db.add(group)
    db.commit()
    return RedirectResponse(url="/groups", status_code=303)


@app.get("/groups/{group_id}/edit", response_class=HTMLResponse)
async def edit_group_page(request: Request, group_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    group = get_group_or_404(group_id, db)
    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()
    return templates.TemplateResponse(name="group_form.html", request=request, context={"request": request, "user": user, "title": "Редактировать группу", "group": group, "coaches": coaches})


@app.post("/groups/{group_id}/edit")
async def edit_group(request: Request, group_id: int, name: str = Form(...), level: int = Form(...), max_capacity: int = Form(12), coach_id: Optional[int] = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    group = get_group_or_404(group_id, db)
    group.name = name
    group.level = level
    group.max_capacity = max_capacity
    group.coach_id = coach_id if coach_id else None
    db.commit()
    return RedirectResponse(url="/groups", status_code=303)


@app.get("/groups/{group_id}/delete")
async def delete_group(request: Request, group_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    group = get_group_or_404(group_id, db)
    group.is_active = False
    db.commit()
    return RedirectResponse(url="/groups", status_code=303)


# ========== ГРУППЫ (API) ==========
@app.get("/api/groups", response_model=List[GroupResponse])
async def api_get_groups(coach_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(GroupDB).filter(GroupDB.is_active == True)
    if coach_id:
        query = query.filter(GroupDB.coach_id == coach_id)
    groups = query.all()
    result = []
    for group in groups:
        current_count = db.query(EnrollmentDB).filter(
            EnrollmentDB.group_id == group.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).count()
        result.append(GroupResponse(
            id=group.id, name=group.name, level=group.level,
            coach_id=group.coach_id, coach_name=group.coach.name if group.coach else None,
            max_capacity=group.max_capacity, current_enrollment=current_count, is_active=group.is_active
        ))
    return result


@app.get("/api/groups/{group_id}", response_model=GroupResponse)
async def api_get_group(group_id: int, db: Session = Depends(get_db)):
    group = get_group_or_404(group_id, db)
    current_count = db.query(EnrollmentDB).filter(
        EnrollmentDB.group_id == group.id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).count()
    return GroupResponse(
        id=group.id, name=group.name, level=group.level,
        coach_id=group.coach_id, coach_name=group.coach.name if group.coach else None,
        max_capacity=group.max_capacity, current_enrollment=current_count, is_active=group.is_active
    )


@app.post("/api/groups", response_model=GroupResponse, status_code=201)
async def api_create_group(group_data: GroupCreate, db: Session = Depends(get_db)):
    group = GroupDB(
        name=group_data.name, level=group_data.level,
        coach_id=group_data.coach_id, max_capacity=group_data.max_capacity
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return GroupResponse(
        id=group.id, name=group.name, level=group.level,
        coach_id=group.coach_id, coach_name=group.coach.name if group.coach else None,
        max_capacity=group.max_capacity, current_enrollment=0, is_active=group.is_active
    )


@app.put("/api/groups/{group_id}", response_model=GroupResponse)
async def api_update_group(group_id: int, group_data: GroupCreate, db: Session = Depends(get_db)):
    group = get_group_or_404(group_id, db)
    group.name = group_data.name
    group.level = group_data.level
    group.coach_id = group_data.coach_id
    group.max_capacity = group_data.max_capacity
    db.commit()
    db.refresh(group)
    current_count = db.query(EnrollmentDB).filter(
        EnrollmentDB.group_id == group.id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).count()
    return GroupResponse(
        id=group.id, name=group.name, level=group.level,
        coach_id=group.coach_id, coach_name=group.coach.name if group.coach else None,
        max_capacity=group.max_capacity, current_enrollment=current_count, is_active=group.is_active
    )


@app.delete("/api/groups/{group_id}")
async def api_delete_group(group_id: int, db: Session = Depends(get_db)):
    group = get_group_or_404(group_id, db)
    group.is_active = False
    db.commit()
    return {"message": "Group deleted"}


# ========== ТРЕНЕРЫ (ВЕБ) ==========
@app.get("/trainers", response_class=HTMLResponse)
async def trainers_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()
    coaches_data = []
    for coach in coaches:
        groups_count = db.query(GroupDB).filter(GroupDB.coach_id == coach.id, GroupDB.is_active == True).count()
        coaches_data.append({"id": coach.id, "name": coach.name, "email": coach.email, "phone": coach.phone, "groups_count": groups_count, "is_active": coach.is_active})
    return templates.TemplateResponse(name="trainers.html", request=request, context={"request": request, "user": user, "coaches": coaches_data})


@app.get("/trainers/add", response_class=HTMLResponse)
async def add_trainer_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(name="trainer_form.html", request=request, context={"request": request, "user": user, "title": "Добавить тренера", "coach": {}})


@app.post("/trainers/add")
async def add_trainer(request: Request, name: str = Form(...), email: str = Form(...), phone: Optional[str] = Form(None), password: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    existing = db.query(CoachDB).filter(CoachDB.email == email).first()
    if existing:
        coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()
        return templates.TemplateResponse(name="trainer_form.html", request=request, context={"request": request, "user": user, "title": "Добавить тренера", "coach": {}, "error": "Тренер с таким email уже существует"})
    coach = CoachDB(name=name, email=email, phone=phone, password=password)
    db.add(coach)
    db.commit()
    return RedirectResponse(url="/trainers", status_code=303)


@app.get("/trainers/{coach_id}/edit", response_class=HTMLResponse)
async def edit_trainer_page(request: Request, coach_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    coach = get_coach_or_404(coach_id, db)
    return templates.TemplateResponse(name="trainer_form.html", request=request, context={"request": request, "user": user, "title": "Редактировать тренера", "coach": coach})


@app.post("/trainers/{coach_id}/edit")
async def edit_trainer(request: Request, coach_id: int, name: str = Form(...), email: str = Form(...), phone: Optional[str] = Form(None), password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    coach = get_coach_or_404(coach_id, db)
    coach.name = name
    coach.email = email
    coach.phone = phone
    if password:
        coach.password = password
    db.commit()
    return RedirectResponse(url="/trainers", status_code=303)


@app.get("/trainers/{coach_id}/delete")
async def delete_trainer(request: Request, coach_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    coach = get_coach_or_404(coach_id, db)
    coach.is_active = False
    db.commit()
    return RedirectResponse(url="/trainers", status_code=303)


# ========== ТРЕНИРОВКИ ==========
@app.get("/trainings", response_class=HTMLResponse)
async def trainings_list(request: Request, group_id: Optional[int] = Query(None), status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    query = db.query(TrainingDB)
    if user["role"] == "coach":
        coach_groups = db.query(GroupDB.id).filter(GroupDB.coach_id == user["id"]).subquery()
        query = query.filter(TrainingDB.group_id.in_(coach_groups))
    if group_id:
        query = query.filter(TrainingDB.group_id == group_id)
    if status:
        query = query.filter(TrainingDB.status == status)
    trainings = query.order_by(TrainingDB.date.desc()).limit(100).all()
    trainings_data = []
    for training in trainings:
        trainings_data.append({
            "id": training.id, "date": training.date,
            "group_name": training.group.name if training.group else "Unknown",
            "start_time": training.start_time.strftime("%H:%M") if training.start_time else "00:00",
            "end_time": training.end_time.strftime("%H:%M") if training.end_time else "00:00",
            "status": training.status.value if training.status else "scheduled"
        })
    groups_query = db.query(GroupDB).filter(GroupDB.is_active == True)
    if user["role"] == "coach":
        groups_query = groups_query.filter(GroupDB.coach_id == user["id"])
    groups = groups_query.all()
    return templates.TemplateResponse(name="trainings.html", request=request, context={"request": request, "user": user, "trainings": trainings_data, "groups": groups, "filters": {"group_id": group_id, "status": status}})


@app.get("/trainings/generate")
async def generate_trainings(request: Request, group_id: Optional[int] = Query(None), months: int = Query(1), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    if group_id:
        groups = db.query(GroupDB).filter(GroupDB.id == group_id, GroupDB.is_active == True).all()
    else:
        groups = db.query(GroupDB).filter(GroupDB.is_active == True).all()
    if not groups:
        return RedirectResponse(url="/trainings?error=Нет активных групп")
    today = date.today()
    created_count = 0
    for group in groups:
        time_slots = db.query(TimeSlotDB).filter(TimeSlotDB.group_id == group.id).all()
        if not time_slots:
            continue
        for month_offset in range(months):
            year = today.year
            month = today.month + month_offset
            while month > 12:
                month -= 12
                year += 1
            first_day = date(year, month, 1)
            if month == 12:
                last_day = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(year, month + 1, 1) - timedelta(days=1)
            current_date = first_day
            while current_date <= last_day:
                for slot in time_slots:
                    if slot.day_of_week == current_date.weekday():
                        existing = db.query(TrainingDB).filter(
                            TrainingDB.group_id == group.id,
                            TrainingDB.date == current_date,
                            TrainingDB.time_slot_id == slot.id
                        ).first()
                        if not existing:
                            training = TrainingDB(
                                group_id=group.id, time_slot_id=slot.id,
                                date=current_date, start_time=slot.start_time,
                                end_time=slot.end_time, status=TrainingStatus.SCHEDULED
                            )
                            db.add(training)
                            created_count += 1
                current_date += timedelta(days=1)
    db.commit()
    return RedirectResponse(url=f"/trainings?success=Создано {created_count} тренировок", status_code=303)


# ========== ПОСЕЩАЕМОСТЬ ==========
@app.get("/attendance", response_class=HTMLResponse)
async def attendance_page(request: Request, training_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    trainings_query = db.query(TrainingDB)
    if user["role"] == "coach":
        coach_groups = db.query(GroupDB.id).filter(GroupDB.coach_id == user["id"]).subquery()
        trainings_query = trainings_query.filter(TrainingDB.group_id.in_(coach_groups))
    trainings = trainings_query.order_by(TrainingDB.date.desc()).limit(50).all()
    trainings_data = [{"id": t.id, "date": t.date, "group_name": t.group.name if t.group else "Unknown", "start_time": t.start_time.strftime("%H:%M") if t.start_time else "00:00"} for t in trainings]
    attendance_list = []
    if training_id:
        training = get_training_or_404(training_id, db)
        enrollments = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == training.group_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).all()
        if user["role"] == "parent":
            children_ids = [c.id for c in db.query(ChildDB).filter(ChildDB.parent_id == user["id"]).all()]
            enrollments = [e for e in enrollments if e.child_id in children_ids]
        for enrollment in enrollments:
            attendance = db.query(AttendanceDB).filter(AttendanceDB.training_id == training_id, AttendanceDB.child_id == enrollment.child_id).first()
            attendance_list.append({"child_id": enrollment.child.id, "child_name": enrollment.child.name, "status": attendance.status.value if attendance else "not_marked"})
    return templates.TemplateResponse(name="attendance.html", request=request, context={"request": request, "user": user, "trainings": trainings_data, "selected_training_id": training_id, "attendance_list": attendance_list})


@app.post("/attendance/save")
async def save_attendance(request: Request, training_id: int = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] not in ["coach", "admin"]:
        return RedirectResponse(url="/dashboard")
    form_data = await request.form()
    from vk_bot import send_attendance_notification_vk
    for key, value in form_data.items():
        if key.startswith("status_"):
            child_id = int(key.split("_")[1])
            training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
            if training:
                group = db.query(GroupDB).filter(GroupDB.id == training.group_id).first()
                if group and (user["role"] == "admin" or group.coach_id == user["id"]):
                    existing = db.query(AttendanceDB).filter(AttendanceDB.training_id == training_id, AttendanceDB.child_id == child_id).first()
                    if existing:
                        existing.status = value
                        existing.marked_at = datetime.now().strftime("%d.%m.%Y %H:%M")
                    else:
                        attendance = AttendanceDB(training_id=training_id, child_id=child_id, status=value, marked_by=f"coach_{user['id']}" if user["role"] == "coach" else "admin")
                        db.add(attendance)
                    try:
                        send_attendance_notification_vk(child_id=child_id, training_id=training_id, status=value, db=db)
                    except Exception as e:
                        print(f"Ошибка VK: {e}")
    db.commit()
    return RedirectResponse(url=f"/attendance?training_id={training_id}", status_code=303)


# ========== ЗАЯВКИ ==========
@app.get("/applications", response_class=HTMLResponse)
async def applications_list(request: Request, status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    query = db.query(ApplicationDB).order_by(ApplicationDB.created_at.desc())
    if status:
        query = query.filter(ApplicationDB.status == status)
    applications = query.all()
    apps_data = []
    for app in applications:
        group = app.group
        group_is_full = False
        if group:
            current_enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == group.id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).count()
            group_is_full = current_enrollment >= group.max_capacity
        child_name = None
        child_birthdate = None
        child_class = None
        medical_cert_date = None
        medical_note = None
        if app.child:
            child_name = app.child.name
            child_birthdate = app.child.birthdate
            child_class = app.child.class_num
            medical_cert_date = app.child.medical_date
            medical_note = app.child.medical_note
        elif app.public_child_name:
            child_name = app.public_child_name
            child_birthdate = app.public_child_birthdate
            child_class = app.public_child_class
            medical_cert_date = app.public_child_medical_date
            medical_note = app.public_child_medical_note
        apps_data.append({
            "id": app.id, "parent_name": app.parent.name if app.parent else None,
            "parent_phone": app.parent.phone if app.parent else None,
            "parent_email": app.parent.email if app.parent else None,
            "public_parent_name": app.public_parent_name, "public_parent_phone": app.public_parent_phone,
            "public_parent_email": app.public_parent_email, "child_name": child_name,
            "public_child_name": app.public_child_name, "child_birthdate": child_birthdate,
            "public_child_birthdate": app.public_child_birthdate, "child_class": child_class,
            "public_child_class": app.public_child_class, "medical_cert_date": medical_cert_date,
            "medical_note": medical_note, "group_name": app.group.name if app.group else "Unknown",
            "status": app.status.value if app.status else "new", "created_at": app.created_at, "group_is_full": group_is_full
        })
    return templates.TemplateResponse(name="applications.html", request=request, context={"request": request, "user": user, "applications": apps_data, "filters": {"status": status}})


@app.get("/applications/{app_id}")
async def application_detail(request: Request, app_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if not application:
        return RedirectResponse(url="/applications")
    group = application.group
    current_enrollment = 0
    group_is_full = False
    if group:
        current_enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.group_id == group.id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).count()
        group_is_full = current_enrollment >= group.max_capacity
    child_name = None
    child_birthdate = None
    child_class = None
    child_study_year = None
    medical_cert_date = None
    medical_note = None
    if application.child:
        child_name = application.child.name
        child_birthdate = application.child.birthdate
        child_class = application.child.class_num
        child_study_year = application.child.study_year
        medical_cert_date = application.child.medical_date
        medical_note = application.child.medical_note
    elif application.public_child_name:
        child_name = application.public_child_name
        child_birthdate = application.public_child_birthdate
        child_class = application.public_child_class
        child_study_year = application.public_child_study_year
        medical_cert_date = application.public_child_medical_date
        medical_note = application.public_child_medical_note
    app_data = {
        "id": application.id, "parent_name": application.parent.name if application.parent else None,
        "parent_phone": application.parent.phone if application.parent else None,
        "parent_email": application.parent.email if application.parent else None,
        "public_parent_name": application.public_parent_name, "public_parent_phone": application.public_parent_phone,
        "public_parent_email": application.public_parent_email, "child_name": child_name,
        "public_child_name": application.public_child_name, "child_birthdate": child_birthdate,
        "public_child_birthdate": application.public_child_birthdate, "child_class": child_class,
        "public_child_class": application.public_child_class, "child_study_year": child_study_year,
        "public_child_study_year": application.public_child_study_year, "medical_cert_date": medical_cert_date,
        "medical_note": medical_note, "group_name": group.name if group else "Unknown",
        "group_level": group.level if group else 0, "group_max_capacity": group.max_capacity if group else 0,
        "group_current_enrollment": current_enrollment, "group_coach_name": group.coach.name if group and group.coach else None,
        "group_is_full": group_is_full, "status": application.status.value if application.status else "new",
        "created_at": application.created_at, "admin_comment": application.admin_comment
    }
    return templates.TemplateResponse(name="application_detail.html", request=request, context={"request": request, "user": user, "application": app_data})


@app.get("/applications/{app_id}/approve")
async def approve_application(request: Request, app_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if not application:
        return RedirectResponse(url="/applications")
    application.status = ApplicationStatus.APPROVED
    parent = None
    if not application.parent_id and application.public_parent_email:
        parent = db.query(ParentDB).filter(ParentDB.email == application.public_parent_email).first()
        if not parent:
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            parent = ParentDB(name=application.public_parent_name, email=application.public_parent_email, phone=application.public_parent_phone, password=temp_password, is_active=True)
            db.add(parent)
            db.flush()
        application.parent_id = parent.id
    if not application.child_id and application.public_child_name:
        child = ChildDB(parent_id=application.parent_id, name=application.public_child_name, birthdate=application.public_child_birthdate, class_num=application.public_child_class, study_year=application.public_child_study_year, medical_date=application.public_child_medical_date, medical_note=application.public_child_medical_note)
        db.add(child)
        db.flush()
        application.child_id = child.id
    if application.child_id and application.group_id:
        enrollment = EnrollmentDB(child_id=application.child_id, group_id=application.group_id, status=EnrollmentStatus.ACTIVE, start_date=date.today())
        db.add(enrollment)
    db.commit()
    return RedirectResponse(url="/applications", status_code=303)


@app.get("/applications/{app_id}/reject")
async def reject_application(request: Request, app_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if application:
        application.status = ApplicationStatus.REJECTED
        db.commit()
    return RedirectResponse(url="/applications", status_code=303)


@app.get("/applications/{app_id}/waiting")
async def waiting_application(request: Request, app_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if application:
        application.status = ApplicationStatus.WAITING_LIST
        db.commit()
    return RedirectResponse(url="/applications", status_code=303)


@app.post("/applications/{app_id}/comment")
async def application_comment(request: Request, app_id: int, admin_comment: str = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if application:
        application.admin_comment = admin_comment
        db.commit()
    return RedirectResponse(url=f"/applications/{app_id}", status_code=303)


# ========== ПЕРЕВОДЫ ==========
@app.get("/transfers", response_class=HTMLResponse)
async def transfers_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    query = db.query(TransferRequestDB).order_by(TransferRequestDB.created_at.desc())
    if user["role"] == "coach":
        query = query.filter(TransferRequestDB.coach_id == user["id"])
    transfers = query.all()
    transfers_data = [{"id": t.id, "child_name": t.child.name if t.child else "Unknown", "from_group_name": t.from_group.name if t.from_group else None, "suggested_group_name": t.suggested_group.name if t.suggested_group else None, "coach_name": t.coach.name if t.coach else "Unknown", "comment": t.comment or "", "status": t.status, "created_at": t.created_at} for t in transfers]
    return templates.TemplateResponse(name="transfers.html", request=request, context={"request": request, "user": user, "transfers": transfers_data})


@app.get("/transfers/add", response_class=HTMLResponse)
async def add_transfer_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "coach":
        return RedirectResponse(url="/dashboard")
    coach_groups = db.query(GroupDB.id).filter(GroupDB.coach_id == user["id"], GroupDB.is_active == True).all()
    group_ids = [g[0] for g in coach_groups]
    children_in_groups = []
    if group_ids:
        children_query = db.query(ChildDB).join(EnrollmentDB, EnrollmentDB.child_id == ChildDB.id).filter(EnrollmentDB.group_id.in_(group_ids), EnrollmentDB.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.WAITING_LIST]), ChildDB.is_active == True).distinct()
        for child in children_query.all():
            enrollments = db.query(EnrollmentDB).filter(EnrollmentDB.child_id == child.id, EnrollmentDB.group_id.in_(group_ids), EnrollmentDB.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.WAITING_LIST])).all()
            for enrollment in enrollments:
                children_in_groups.append({"id": child.id, "name": child.name, "group_id": enrollment.group_id, "group_name": enrollment.group.name if enrollment.group else "Unknown", "status": enrollment.status.value, "type": "in_group"})
    children_without_group = db.query(ChildDB).filter(ChildDB.is_active == True, ~ChildDB.enrollments.any(EnrollmentDB.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.WAITING_LIST]))).all()
    children_without_group_data = [{"id": child.id, "name": child.name, "group_id": None, "group_name": "Без группы (ожидает зачисления)", "status": "no_group", "type": "without_group", "birthdate": child.birthdate, "class_num": child.class_num, "study_year": child.study_year} for child in children_without_group]
    all_children = children_in_groups + children_without_group_data
    groups = db.query(GroupDB).filter(GroupDB.is_active == True, GroupDB.coach_id == user["id"]).all()
    groups_data = [{"id": g.id, "name": g.name, "current_enrollment": get_group_enrollment_count(g.id, db), "max_capacity": g.max_capacity, "has_free_places": get_group_enrollment_count(g.id, db) < g.max_capacity} for g in groups]
    for child in children_without_group_data:
        child_obj = db.query(ChildDB).filter(ChildDB.id == child["id"]).first()
        if child_obj and child_obj.parent:
            child["parent_name"] = child_obj.parent.name
            child["parent_phone"] = child_obj.parent.phone
    return templates.TemplateResponse(name="transfer_form.html", request=request, context={"request": request, "user": user, "children": all_children, "groups": groups_data, "has_children_in_groups": len(children_in_groups) > 0, "has_children_without_group": len(children_without_group_data) > 0})


@app.post("/transfers/add")
async def add_transfer(request: Request, child_id: int = Form(...), from_group_id: Optional[int] = Form(None), suggested_group_id: Optional[int] = Form(None), comment: Optional[str] = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "coach":
        return RedirectResponse(url="/dashboard")
    child = db.query(ChildDB).filter(ChildDB.id == child_id, ChildDB.is_active == True).first()
    if not child:
        return RedirectResponse(url="/transfers/add?error=child_not_found")
    is_new_child = not from_group_id or from_group_id == 0
    existing = db.query(TransferRequestDB).filter(TransferRequestDB.child_id == child_id, TransferRequestDB.status == "pending").first()
    if existing:
        return RedirectResponse(url="/transfers?error=already_exists")
    transfer = TransferRequestDB(coach_id=user["id"], child_id=child_id, from_group_id=from_group_id if from_group_id and not is_new_child else None, suggested_group_id=suggested_group_id if suggested_group_id else None, comment=comment, status="pending")
    db.add(transfer)
    db.commit()
    return RedirectResponse(url="/transfers", status_code=303)


@app.get("/transfers/{transfer_id}/approve")
async def approve_transfer(request: Request, transfer_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    transfer = db.query(TransferRequestDB).filter(TransferRequestDB.id == transfer_id).first()
    if not transfer:
        return RedirectResponse(url="/transfers")
    transfer.status = "approved"
    if not transfer.from_group_id:
        if transfer.suggested_group_id:
            group = db.query(GroupDB).filter(GroupDB.id == transfer.suggested_group_id).first()
            if group:
                current_count = get_group_enrollment_count(group.id, db)
                if current_count < group.max_capacity:
                    new_enrollment = EnrollmentDB(child_id=transfer.child_id, group_id=transfer.suggested_group_id, status=EnrollmentStatus.ACTIVE, start_date=date.today())
                else:
                    new_enrollment = EnrollmentDB(child_id=transfer.child_id, group_id=transfer.suggested_group_id, status=EnrollmentStatus.WAITING_LIST, start_date=date.today())
                db.add(new_enrollment)
        history = TransferHistoryDB(child_id=transfer.child_id, from_group_id=None, to_group_id=transfer.suggested_group_id, reason=transfer.comment or "Новое зачисление", created_by=f"admin (request by coach {transfer.coach_id})")
        db.add(history)
    else:
        enrollment = db.query(EnrollmentDB).filter(EnrollmentDB.child_id == transfer.child_id, EnrollmentDB.group_id == transfer.from_group_id, EnrollmentDB.status == EnrollmentStatus.ACTIVE).first()
        if enrollment and transfer.suggested_group_id:
            enrollment.status = EnrollmentStatus.COMPLETED
            enrollment.end_date = date.today()
            group = db.query(GroupDB).filter(GroupDB.id == transfer.suggested_group_id).first()
            if group:
                current_count = get_group_enrollment_count(group.id, db)
                if current_count < group.max_capacity:
                    new_enrollment = EnrollmentDB(child_id=transfer.child_id, group_id=transfer.suggested_group_id, status=EnrollmentStatus.ACTIVE, start_date=date.today())
                else:
                    new_enrollment = EnrollmentDB(child_id=transfer.child_id, group_id=transfer.suggested_group_id, status=EnrollmentStatus.WAITING_LIST, start_date=date.today())
                db.add(new_enrollment)
            history = TransferHistoryDB(child_id=transfer.child_id, from_group_id=transfer.from_group_id, to_group_id=transfer.suggested_group_id, reason=transfer.comment, created_by=f"admin (request by coach {transfer.coach_id})")
            db.add(history)
    db.commit()
    return RedirectResponse(url="/transfers", status_code=303)


@app.get("/transfers/{transfer_id}/reject")
async def reject_transfer(request: Request, transfer_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")
    transfer = db.query(TransferRequestDB).filter(TransferRequestDB.id == transfer_id).first()
    if transfer:
        transfer.status = "rejected"
        db.commit()
    return RedirectResponse(url="/transfers", status_code=303)


# ========== ПРОФИЛЬ РОДИТЕЛЯ ==========
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    parent = db.query(ParentDB).filter(ParentDB.id == user["id"]).first()
    vk_code = parent.vk_link_code
    if not vk_code or (parent.vk_code_expires_at and parent.vk_code_expires_at < datetime.now()):
        vk_code = ''.join(random.choices(string.digits, k=6))
        parent.vk_link_code = vk_code
        parent.vk_code_expires_at = datetime.now() + timedelta(minutes=10)
        db.commit()
    return templates.TemplateResponse(name="profile.html", request=request, context={"request": request, "user": user, "parent": parent, "vk_code": vk_code})


@app.post("/profile")
async def update_profile(request: Request, name: str = Form(...), email: str = Form(...), phone: str = Form(...), password: Optional[str] = Form(None), confirm_password: Optional[str] = Form(None), notify_absences: Optional[bool] = Form(False), notify_reminders: Optional[bool] = Form(False), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    parent = db.query(ParentDB).filter(ParentDB.id == user["id"]).first()
    parent.name = name
    parent.email = email
    parent.phone = phone
    parent.notify_absences = notify_absences
    parent.notify_reminders = notify_reminders
    if password:
        if password != confirm_password:
            return templates.TemplateResponse(name="profile.html", request=request, context={"request": request, "user": user, "parent": parent, "error": "Пароли не совпадают"})
        parent.password = password
    db.commit()
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        sessions[session_id]["name"] = name
        sessions[session_id]["email"] = email
    return templates.TemplateResponse(name="profile.html", request=request, context={"request": request, "user": user, "parent": parent, "success": "Профиль обновлён"})


@app.get("/profile/unlink-vk")
async def unlink_vk(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")
    parent = db.query(ParentDB).filter(ParentDB.id == user["id"]).first()
    parent.vk_id = None
    parent.is_vk_linked = False
    db.commit()
    return RedirectResponse(url="/profile", status_code=303)


# ========== VK API ЭНДПОИНТЫ ==========
@app.post("/api/parents/{parent_id}/generate-vk-code")
async def generate_vk_code(parent_id: int, db: Session = Depends(get_db)):
    parent = db.query(ParentDB).filter(ParentDB.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    code = ''.join(random.choices(string.digits, k=6))
    parent.vk_link_code = code
    parent.vk_code_expires_at = datetime.now() + timedelta(minutes=10)
    db.commit()
    return {"code": code, "expires_in": 600}


# ========== ГАЛЕРЕЯ ==========
os.makedirs("static/uploads/gallery", exist_ok=True)
os.makedirs("static/uploads/thumbs", exist_ok=True)


def create_thumbnail(input_path, output_path, size=(300, 200)):
    try:
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(output_path, 'JPEG', quality=85)
            return True
    except Exception as e:
        print(f"Ошибка создания миниатюры: {e}")
        return False


@app.get("/gallery", response_class=HTMLResponse)
async def gallery_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    images = db.query(GalleryImageDB).filter(GalleryImageDB.is_active == True).order_by(GalleryImageDB.sort_order, GalleryImageDB.created_at.desc()).all()
    images_data = [{"id": img.id, "title": img.title, "description": img.description, "filename": img.filename, "image_type": img.image_type, "coach_name": img.coach.name if img.coach else None, "created_at": img.created_at} for img in images]
    coaches = []
    if user and user["role"] == "admin":
        coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()
    return templates.TemplateResponse(name="gallery.html", request=request, context={"request": request, "user": user, "images": images_data, "coaches": coaches})


@app.post("/gallery/upload")
async def upload_gallery_image(request: Request, title: str = Form(...), description: str = Form(None), image_type: str = Form(...), coach_id: Optional[int] = Form(None), file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        return RedirectResponse(url="/gallery?error=Неподдерживаемый формат файла", status_code=303)
    file_ext = file.filename.split('.')[-1].lower()
    unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(file.filename.encode()).hexdigest()[:8]}.{file_ext}"
    file_path = f"static/uploads/gallery/{unique_name}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    thumb_path = f"static/uploads/thumbs/{unique_name}"
    create_thumbnail(file_path, thumb_path)
    gallery_image = GalleryImageDB(title=title, description=description, filename=unique_name, original_filename=file.filename, file_size=os.path.getsize(file_path), image_type=image_type, coach_id=coach_id if coach_id and image_type == 'coach' else None, created_by=user["name"], is_active=True)
    db.add(gallery_image)
    db.commit()
    return RedirectResponse(url="/gallery?success=Изображение загружено", status_code=303)


@app.post("/gallery/{image_id}/delete")
async def delete_gallery_image(request: Request, image_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    image = db.query(GalleryImageDB).filter(GalleryImageDB.id == image_id).first()
    if image:
        file_path = f"static/uploads/gallery/{image.filename}"
        thumb_path = f"static/uploads/thumbs/{image.filename}"
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        db.delete(image)
        db.commit()
    return RedirectResponse(url="/gallery?success=Изображение удалено", status_code=303)


@app.post("/gallery/{image_id}/reorder")
async def reorder_gallery_image(request: Request, image_id: int, action: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    image = db.query(GalleryImageDB).filter(GalleryImageDB.id == image_id).first()
    if not image:
        return RedirectResponse(url="/gallery?error=Изображение не найдено", status_code=303)
    if action == 'up':
        prev = db.query(GalleryImageDB).filter(GalleryImageDB.sort_order < image.sort_order).order_by(GalleryImageDB.sort_order.desc()).first()
        if prev:
            prev.sort_order, image.sort_order = image.sort_order, prev.sort_order
    elif action == 'down':
        next_img = db.query(GalleryImageDB).filter(GalleryImageDB.sort_order > image.sort_order).order_by(GalleryImageDB.sort_order.asc()).first()
        if next_img:
            next_img.sort_order, image.sort_order = image.sort_order, next_img.sort_order
    db.commit()
    return RedirectResponse(url="/gallery", status_code=303)


# ========== ЗАПУСК ==========
if __name__ == "__main__":
    import uvicorn
    print("🐬 Запуск Pool CRM сервера...")
    print("📍 Адрес: http://127.0.0.1:8000")
    print("🔑 Тестовые учётные записи:")
    print("   👑 Админ: admin@pool.ru / admin123")
    print("   👨‍👩‍👧 Родители: maria@example.com / parent123")
    print("   🏊‍♂️ Тренеры: ivan.coach@pool.ru / coach123")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)