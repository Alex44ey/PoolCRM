# main.py (исправленная версия - скопируйте полностью)

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, date, timedelta
import random
import string
import os

from database import (
    engine, Base, SessionLocal, get_db,
    ParentDB, ChildDB, CoachDB, GroupDB, TimeSlotDB,
    EnrollmentDB, ApplicationDB, TrainingDB, AttendanceDB,
    TransferRequestDB, TransferHistoryDB, NotificationDB,
    UserRole, EnrollmentStatus, TrainingStatus, AttendanceStatus,
    ApplicationStatus
)


# ========== НАСТРОЙКА ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск приложения...")
    Base.metadata.create_all(bind=engine)
    print("✅ Приложение готово!")
    yield


app = FastAPI(title="Pool CRM", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создаем папку templates если её нет
os.makedirs("templates", exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Хранилище сессий
sessions = {}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_current_user(request: Request, db: Session):
    """Получение текущего пользователя из сессии"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None

    user_data = sessions[session_id]

    # Для администратора возвращаем словарь с ролью admin
    if user_data["role"] == "admin":
        return {
            "id": user_data["id"],
            "name": user_data["name"],
            "email": user_data["email"],
            "role": "admin"
        }

    # Для родителя получаем из БД
    if user_data["role"] == "parent":
        user = db.query(ParentDB).filter(ParentDB.id == user_data["id"]).first()
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

    # Для тренера получаем из БД
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
    """Получение объекта пользователя из БД (для операций с БД)"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None

    user_data = sessions[session_id]

    if user_data["role"] == "admin":
        return None  # Админ не в БД

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


# ========== АУТЕНТИФИКАЦИЯ ==========
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Главная страница"""
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        name = "index.html",
        request = request,
        context = {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, message: str = None, db: Session = Depends(get_db)):
    """Страница входа"""
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        name = "login.html", 
        request = request,
        context = {
        "request": request,
        "error": error,
        "message": message
    })


@app.post("/login")
async def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    """Обработка входа"""
    # Проверка администратора
    if email == "admin@pool.ru" and password == "admin123":
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sessions[session_id] = {"id": 1, "role": "admin", "name": "Администратор", "email": email}
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    # Проверка родителя
    parent = db.query(ParentDB).filter(
        ParentDB.email == email,
        ParentDB.password == password,
        ParentDB.is_active == True
    ).first()

    if parent:
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sessions[session_id] = {"id": parent.id, "role": "parent", "name": parent.name, "email": parent.email}
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    # Проверка тренера
    coach = db.query(CoachDB).filter(
        CoachDB.email == email,
        CoachDB.password == password,
        CoachDB.is_active == True
    ).first()

    if coach:
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sessions[session_id] = {"id": coach.id, "role": "coach", "name": coach.name, "email": coach.email}
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    return await login_page(request, error="Неверный email или пароль")


@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_id")
    return response


# ========== РЕГИСТРАЦИЯ (ЗАЯВКА ОТ РОДИТЕЛЯ) ==========
@app.get("/register", response_class=HTMLResponse)
async def register_page(
        request: Request,
        child_birthdate: str = None,
        child_study_year: str = None,
        group_id: str = None,
        db: Session = Depends(get_db)
):
    """Страница регистрации/подачи заявки"""
    groups = db.query(GroupDB).filter(GroupDB.is_active == True).all()

    groups_data = []
    for group in groups:
        current_enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.group_id == group.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).count()
        groups_data.append({
            "id": group.id,
            "name": group.name,
            "level": group.level,
            "max_capacity": group.max_capacity,
            "current_enrollment": current_enrollment,
            "has_free_places": current_enrollment < group.max_capacity
        })

    selected_group_id = int(group_id) if group_id else None
    form_data = {}

    return templates.TemplateResponse(
        name = "register.html",
        request = request,
        context = {
        "request": request,
        "groups": groups_data,
        "selected_group_id": selected_group_id,
        "form_data": form_data
    })


@app.post("/register")
async def register(
        request: Request,
        parent_name: str = Form(...),
        parent_phone: str = Form(...),
        parent_email: str = Form(...),
        child_name: str = Form(...),
        child_birthdate: str = Form(...),
        child_class: int = Form(None),
        child_study_year: int = Form(None),
        has_medical_cert: Optional[bool] = Form(False),
        medical_cert_date: Optional[str] = Form(None),
        medical_note: Optional[str] = Form(None),
        group_id: int = Form(...),
        db: Session = Depends(get_db)
):
    """Обработка заявки от родителя"""

    # Проверка группы
    group = db.query(GroupDB).filter(GroupDB.id == group_id, GroupDB.is_active == True).first()
    if not group:
        return await register_page(request, error="Группа не найдена")

    # Проверка свободных мест
    current_enrollment = db.query(EnrollmentDB).filter(
        EnrollmentDB.group_id == group_id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).count()

    if current_enrollment >= group.max_capacity:
        status = ApplicationStatus.WAITING_LIST
    else:
        status = ApplicationStatus.NEW

    # Создаём заявку
    application = ApplicationDB(
        group_id=group_id,
        status=status,
        public_parent_name=parent_name,
        public_parent_phone=parent_phone,
        public_parent_email=parent_email,
        public_child_name=child_name,
        public_child_birthdate=datetime.strptime(child_birthdate, "%Y-%m-%d").date() if child_birthdate else None,
        public_child_class=child_class,
        public_child_study_year=child_study_year,
        public_child_medical_date=datetime.strptime(medical_cert_date,
                                                    "%Y-%m-%d").date() if medical_cert_date and has_medical_cert else None,
        public_child_medical_note=medical_note
    )
    db.add(application)
    db.commit()

    return templates.TemplateResponse(
        name = "login.html", 
        request = request,
        context = {
        "request": request,
        "message": "Заявка успешно отправлена! После рассмотрения администратором вы получите доступ к системе."
    })


# ========== ДАШБОРД ==========
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Панель управления"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")

    # Статистика
    children_count = db.query(ChildDB).filter(ChildDB.is_active == True).count()
    groups_count = db.query(GroupDB).filter(GroupDB.is_active == True).count()
    coaches_count = db.query(CoachDB).filter(CoachDB.is_active == True).count()

    today = date.today()
    trainings_this_month = db.query(TrainingDB).filter(
        TrainingDB.date >= date(today.year, today.month, 1),
        TrainingDB.date <= date(today.year, today.month, 28)
    ).count()

    attendances = db.query(AttendanceDB).filter(AttendanceDB.status == AttendanceStatus.PRESENT).count()
    total_attendances = db.query(AttendanceDB).count()
    attendance_rate = round((attendances / total_attendances * 100) if total_attendances > 0 else 0)

    pending_applications = db.query(ApplicationDB).filter(
        ApplicationDB.status.in_([ApplicationStatus.NEW, ApplicationStatus.ON_REVIEW])
    ).count()

    stats = {
        "children": children_count,
        "groups": groups_count,
        "coaches": coaches_count,
        "trainings_this_month": trainings_this_month,
        "attendance_rate": attendance_rate,
        "pending_applications": pending_applications
    }

    # Для родителя - список детей
    user_children = []
    if user["role"] == "parent":
        children = db.query(ChildDB).filter(ChildDB.parent_id == user["id"], ChildDB.is_active == True).all()
        for child in children:
            enrollment = db.query(EnrollmentDB).filter(
                EnrollmentDB.child_id == child.id,
                EnrollmentDB.status == EnrollmentStatus.ACTIVE
            ).first()
            user_children.append({
                "id": child.id,
                "name": child.name,
                "birthdate": child.birthdate,
                "class_num": child.class_num,
                "group_name": enrollment.group.name if enrollment else None,
                "is_active": child.is_active
            })

    user["children"] = user_children

    return templates.TemplateResponse(
        name = "dashboard.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "stats": stats
    })


# ========== ДЕТИ ==========
@app.get("/children", response_class=HTMLResponse)
async def children_list(request: Request, db: Session = Depends(get_db)):
    """Список детей"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")

    query = db.query(ChildDB).filter(ChildDB.is_active == True)

    if user["role"] == "parent":
        query = query.filter(ChildDB.parent_id == user["id"])

    children = query.all()

    children_data = []
    for child in children:
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()
        children_data.append({
            "id": child.id,
            "name": child.name,
            "birthdate": child.birthdate,
            "class_num": child.class_num,
            "study_year": child.study_year,
            "group_name": enrollment.group.name if enrollment else None,
            "is_active": child.is_active
        })

    return templates.TemplateResponse(
        name = "children.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "children": children_data
    })


@app.get("/children/add", response_class=HTMLResponse)
async def add_child_page(request: Request, db: Session = Depends(get_db)):
    """Страница добавления ребёнка"""
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")

    return templates.TemplateResponse(
        name = "child_form.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "title": "Добавить ребёнка",
        "child": {}
    })


@app.post("/children/add")
async def add_child(
        request: Request,
        name: str = Form(...),
        birthdate: str = Form(...),
        class_num: Optional[int] = Form(None),
        study_year: Optional[int] = Form(None),
        medical_note: Optional[str] = Form(None),
        db: Session = Depends(get_db)
):
    """Добавление ребёнка"""
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")

    child = ChildDB(
        name=name,
        birthdate=datetime.strptime(birthdate, "%Y-%m-%d").date(),
        class_num=class_num,
        study_year=study_year,
        medical_note=medical_note,
        parent_id=user["id"]
    )
    db.add(child)
    db.commit()

    return RedirectResponse(url="/children", status_code=303)


@app.get("/children/{child_id}/edit", response_class=HTMLResponse)
async def edit_child_page(request: Request, child_id: int, db: Session = Depends(get_db)):
    """Страница редактирования ребёнка"""
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")

    child = db.query(ChildDB).filter(ChildDB.id == child_id, ChildDB.parent_id == user["id"]).first()
    if not child:
        return RedirectResponse(url="/children")

    return templates.TemplateResponse(
        name = "child_form.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "title": "Редактировать ребёнка",
        "child": child
    })


@app.post("/children/{child_id}/edit")
async def edit_child(
        request: Request,
        child_id: int,
        name: str = Form(...),
        birthdate: str = Form(...),
        class_num: Optional[int] = Form(None),
        study_year: Optional[int] = Form(None),
        medical_note: Optional[str] = Form(None),
        db: Session = Depends(get_db)
):
    """Редактирование ребёнка"""
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
    """Удаление ребёнка (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
    if child:
        child.is_active = False
        db.commit()

    return RedirectResponse(url="/children", status_code=303)


# ========== ГРУППЫ ==========
@app.get("/groups", response_class=HTMLResponse)
async def groups_list(request: Request, db: Session = Depends(get_db)):
    """Список групп"""
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

    return templates.TemplateResponse(
        name = "groups.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "groups": groups_data
    })


@app.get("/groups/add", response_class=HTMLResponse)
async def add_group_page(request: Request, db: Session = Depends(get_db)):
    """Страница добавления группы (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()

    return templates.TemplateResponse(
        name = "group_form.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "title": "Создать группу",
        "group": {},
        "coaches": coaches
    })


@app.post("/groups/add")
async def add_group(
        request: Request,
        name: str = Form(...),
        level: int = Form(...),
        max_capacity: int = Form(12),
        coach_id: Optional[int] = Form(None),
        db: Session = Depends(get_db)
):
    """Создание группы (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    group = GroupDB(
        name=name,
        level=level,
        max_capacity=max_capacity,
        coach_id=coach_id if coach_id else None
    )
    db.add(group)
    db.commit()

    return RedirectResponse(url="/groups", status_code=303)


@app.get("/groups/{group_id}/edit", response_class=HTMLResponse)
async def edit_group_page(request: Request, group_id: int, db: Session = Depends(get_db)):
    """Страница редактирования группы (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if not group:
        return RedirectResponse(url="/groups")

    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()

    return templates.TemplateResponse(
        name = "group_form.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "title": "Редактировать группу",
        "group": group,
        "coaches": coaches
    })


@app.post("/groups/{group_id}/edit")
async def edit_group(
        request: Request,
        group_id: int,
        name: str = Form(...),
        level: int = Form(...),
        max_capacity: int = Form(12),
        coach_id: Optional[int] = Form(None),
        db: Session = Depends(get_db)
):
    """Редактирование группы (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if not group:
        return RedirectResponse(url="/groups")

    group.name = name
    group.level = level
    group.max_capacity = max_capacity
    group.coach_id = coach_id if coach_id else None

    db.commit()

    return RedirectResponse(url="/groups", status_code=303)


@app.get("/groups/{group_id}/delete")
async def delete_group(request: Request, group_id: int, db: Session = Depends(get_db)):
    """Удаление группы (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if group:
        group.is_active = False
        db.commit()

    return RedirectResponse(url="/groups", status_code=303)


# ========== ТРЕНЕРЫ ==========
@app.get("/trainers", response_class=HTMLResponse)
async def trainers_list(request: Request, db: Session = Depends(get_db)):
    """Список тренеров (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()

    coaches_data = []
    for coach in coaches:
        groups_count = db.query(GroupDB).filter(GroupDB.coach_id == coach.id, GroupDB.is_active == True).count()
        coaches_data.append({
            "id": coach.id,
            "name": coach.name,
            "email": coach.email,
            "phone": coach.phone,
            "groups_count": groups_count,
            "is_active": coach.is_active
        })

    return templates.TemplateResponse(
        name = "trainers.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "coaches": coaches_data
    })


@app.get("/trainers/add", response_class=HTMLResponse)
async def add_trainer_page(request: Request, db: Session = Depends(get_db)):
    """Страница добавления тренера (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    return templates.TemplateResponse(
        name = "trainer_form.html", 
        request = request,
        context = {
        "request": request,
        "user": user,
        "title": "Добавить тренера",
        "coach": {}
    })


@app.post("/trainers/add")
async def add_trainer(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        phone: Optional[str] = Form(None),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    """Создание тренера (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    # Проверяем, не существует ли уже такой email
    existing = db.query(CoachDB).filter(CoachDB.email == email).first()
    if existing:
        return templates.TemplateResponse(
            name = "trainer_form.html", 
            request = request,
            context = {
                "request": request,
                "user": user,
                "title": "Добавить тренера",
                "coach": {},
                "error": "Тренер с таким email уже существует"
            })

    coach = CoachDB(
        name=name,
        email=email,
        phone=phone,
        password=password
    )
    db.add(coach)
    db.commit()

    return RedirectResponse(url="/trainers", status_code=303)


@app.get("/trainers/{coach_id}/edit", response_class=HTMLResponse)
async def edit_trainer_page(request: Request, coach_id: int, db: Session = Depends(get_db)):
    """Страница редактирования тренера (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    coach = db.query(CoachDB).filter(CoachDB.id == coach_id).first()
    if not coach:
        return RedirectResponse(url="/trainers")

    return templates.TemplateResponse(
        name = "trainer_form.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "title": "Редактировать тренера",
            "coach": coach
        })


@app.post("/trainers/{coach_id}/edit")
async def edit_trainer(
        request: Request,
        coach_id: int,
        name: str = Form(...),
        email: str = Form(...),
        phone: Optional[str] = Form(None),
        password: Optional[str] = Form(None),
        db: Session = Depends(get_db)
):
    """Редактирование тренера (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    coach = db.query(CoachDB).filter(CoachDB.id == coach_id).first()
    if not coach:
        return RedirectResponse(url="/trainers")

    coach.name = name
    coach.email = email
    coach.phone = phone
    if password:
        coach.password = password

    db.commit()

    return RedirectResponse(url="/trainers", status_code=303)


@app.get("/trainers/{coach_id}/delete")
async def delete_trainer(request: Request, coach_id: int, db: Session = Depends(get_db)):
    """Удаление тренера (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    coach = db.query(CoachDB).filter(CoachDB.id == coach_id).first()
    if coach:
        coach.is_active = False
        db.commit()

    return RedirectResponse(url="/trainers", status_code=303)


# ========== ТРЕНИРОВКИ ==========
@app.get("/trainings", response_class=HTMLResponse)
async def trainings_list(
        request: Request,
        group_id: Optional[int] = Query(None),
        status: Optional[str] = Query(None),
        db: Session = Depends(get_db)
):
    """Список тренировок"""
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
            "id": training.id,
            "date": training.date,
            "group_name": training.group.name if training.group else "Unknown",
            "start_time": training.start_time.strftime("%H:%M") if training.start_time else "00:00",
            "end_time": training.end_time.strftime("%H:%M") if training.end_time else "00:00",
            "status": training.status.value if training.status else "scheduled"
        })

    # Список групп для фильтра
    groups_query = db.query(GroupDB).filter(GroupDB.is_active == True)
    if user["role"] == "coach":
        groups_query = groups_query.filter(GroupDB.coach_id == user["id"])

    groups = groups_query.all()

    return templates.TemplateResponse(
        name = "trainings.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "trainings": trainings_data,
            "groups": groups,
            "filters": {"group_id": group_id, "status": status}
        })


# ========== ПОСЕЩАЕМОСТЬ ==========
@app.get("/attendance", response_class=HTMLResponse)
async def attendance_page(
        request: Request,
        training_id: Optional[int] = Query(None),
        db: Session = Depends(get_db)
):
    """Страница посещаемости"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")

    # Список тренировок для выбора
    trainings_query = db.query(TrainingDB)

    if user["role"] == "coach":
        coach_groups = db.query(GroupDB.id).filter(GroupDB.coach_id == user["id"]).subquery()
        trainings_query = trainings_query.filter(TrainingDB.group_id.in_(coach_groups))

    trainings = trainings_query.order_by(TrainingDB.date.desc()).limit(50).all()

    trainings_data = []
    for t in trainings:
        trainings_data.append({
            "id": t.id,
            "date": t.date,
            "group_name": t.group.name if t.group else "Unknown",
            "start_time": t.start_time.strftime("%H:%M") if t.start_time else "00:00"
        })

    attendance_list = []
    if training_id:
        training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
        if training:
            # Получаем всех активных детей в группе
            enrollments = db.query(EnrollmentDB).filter(
                EnrollmentDB.group_id == training.group_id,
                EnrollmentDB.status == EnrollmentStatus.ACTIVE
            ).all()

            # Если родитель - фильтруем по его детям
            if user["role"] == "parent":
                children_ids = [c.id for c in db.query(ChildDB).filter(ChildDB.parent_id == user["id"]).all()]
                enrollments = [e for e in enrollments if e.child_id in children_ids]

            for enrollment in enrollments:
                attendance = db.query(AttendanceDB).filter(
                    AttendanceDB.training_id == training_id,
                    AttendanceDB.child_id == enrollment.child_id
                ).first()

                attendance_list.append({
                    "child_id": enrollment.child.id,
                    "child_name": enrollment.child.name,
                    "status": attendance.status.value if attendance else "not_marked"
                })

    return templates.TemplateResponse(
        name = "attendance.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "trainings": trainings_data,
            "selected_training_id": training_id,
            "attendance_list": attendance_list
        })


@app.post("/attendance/save")
async def save_attendance(
        request: Request,
        training_id: int = Form(...),
        db: Session = Depends(get_db)
):
    """Сохранение посещаемости"""
    user = get_current_user(request, db)
    if not user or user["role"] not in ["coach", "admin"]:
        return RedirectResponse(url="/dashboard")

    form_data = await request.form()

    for key, value in form_data.items():
        if key.startswith("status_"):
            child_id = int(key.split("_")[1])

            # Проверка, что тренировка принадлежит тренеру
            training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
            if training:
                group = db.query(GroupDB).filter(GroupDB.id == training.group_id).first()
                if group and (user["role"] == "admin" or group.coach_id == user["id"]):
                    existing = db.query(AttendanceDB).filter(
                        AttendanceDB.training_id == training_id,
                        AttendanceDB.child_id == child_id
                    ).first()

                    if existing:
                        existing.status = value
                        existing.marked_at = datetime.now().strftime("%d.%m.%Y %H:%M")
                    else:
                        attendance = AttendanceDB(
                            training_id=training_id,
                            child_id=child_id,
                            status=value,
                            marked_by=f"coach_{user['id']}" if user["role"] == "coach" else "admin"
                        )
                        db.add(attendance)

    db.commit()

    return RedirectResponse(url=f"/attendance?training_id={training_id}", status_code=303)


# ========== ЗАЯВКИ (АДМИН) ==========
# main.py - найдите функцию applications_list и замените её на эту:

@app.get("/applications", response_class=HTMLResponse)
async def applications_list(
        request: Request,
        status: Optional[str] = Query(None),
        db: Session = Depends(get_db)
):
    """Список заявок (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    query = db.query(ApplicationDB).order_by(ApplicationDB.created_at.desc())

    if status:
        query = query.filter(ApplicationDB.status == status)

    applications = query.all()

    apps_data = []
    for app in applications:
        # Проверка заполненности группы
        group = app.group
        group_is_full = False
        if group:
            current_enrollment = db.query(EnrollmentDB).filter(
                EnrollmentDB.group_id == group.id,
                EnrollmentDB.status == EnrollmentStatus.ACTIVE
            ).count()
            group_is_full = current_enrollment >= group.max_capacity

        # Безопасное получение имени ребёнка
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
            "id": app.id,
            "parent_name": app.parent.name if app.parent else None,
            "parent_phone": app.parent.phone if app.parent else None,
            "parent_email": app.parent.email if app.parent else None,
            "public_parent_name": app.public_parent_name,
            "public_parent_phone": app.public_parent_phone,
            "public_parent_email": app.public_parent_email,
            "child_name": child_name,
            "public_child_name": app.public_child_name,
            "child_birthdate": child_birthdate,
            "public_child_birthdate": app.public_child_birthdate,
            "child_class": child_class,
            "public_child_class": app.public_child_class,
            "medical_cert_date": medical_cert_date,
            "medical_note": medical_note,
            "group_name": app.group.name if app.group else "Unknown",
            "status": app.status.value if app.status else "new",
            "created_at": app.created_at,
            "group_is_full": group_is_full
        })

    return templates.TemplateResponse(
        name = "applications.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "applications": apps_data,
            "filters": {"status": status}
        })


# main.py - найдите функцию application_detail и замените её:

@app.get("/applications/{app_id}")
async def application_detail(request: Request, app_id: int, db: Session = Depends(get_db)):
    """Детали заявки (админ)"""
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
        current_enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.group_id == group.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).count()
        group_is_full = current_enrollment >= group.max_capacity

    # Безопасное получение данных ребёнка
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
        "id": application.id,
        "parent_name": application.parent.name if application.parent else None,
        "parent_phone": application.parent.phone if application.parent else None,
        "parent_email": application.parent.email if application.parent else None,
        "public_parent_name": application.public_parent_name,
        "public_parent_phone": application.public_parent_phone,
        "public_parent_email": application.public_parent_email,
        "child_name": child_name,
        "public_child_name": application.public_child_name,
        "child_birthdate": child_birthdate,
        "public_child_birthdate": application.public_child_birthdate,
        "child_class": child_class,
        "public_child_class": application.public_child_class,
        "child_study_year": child_study_year,
        "public_child_study_year": application.public_child_study_year,
        "medical_cert_date": medical_cert_date,
        "medical_note": medical_note,
        "group_name": group.name if group else "Unknown",
        "group_level": group.level if group else 0,
        "group_max_capacity": group.max_capacity if group else 0,
        "group_current_enrollment": current_enrollment,
        "group_coach_name": group.coach.name if group and group.coach else None,
        "group_is_full": group_is_full,
        "status": application.status.value if application.status else "new",
        "created_at": application.created_at,
        "admin_comment": application.admin_comment
    }

    return templates.TemplateResponse(
        name = "application_detail.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "application": app_data
        })

@app.get("/applications/{app_id}/approve")
async def approve_application(request: Request, app_id: int, db: Session = Depends(get_db)):
    """Одобрение заявки (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if not application:
        return RedirectResponse(url="/applications")

    application.status = ApplicationStatus.APPROVED

    # Создаём родителя если его нет
    parent = None
    if not application.parent_id and application.public_parent_email:
        # Проверяем, не существует ли уже родитель с таким email
        parent = db.query(ParentDB).filter(ParentDB.email == application.public_parent_email).first()
        if not parent:
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            parent = ParentDB(
                name=application.public_parent_name,
                email=application.public_parent_email,
                phone=application.public_parent_phone,
                password=temp_password,
                is_active=True
            )
            db.add(parent)
            db.flush()
        application.parent_id = parent.id

    # Создаём ребёнка
    if not application.child_id and application.public_child_name:
        child = ChildDB(
            parent_id=application.parent_id,
            name=application.public_child_name,
            birthdate=application.public_child_birthdate,
            class_num=application.public_child_class,
            study_year=application.public_child_study_year,
            medical_date=application.public_child_medical_date,
            medical_note=application.public_child_medical_note
        )
        db.add(child)
        db.flush()
        application.child_id = child.id

    # Создаём зачисление
    if application.child_id and application.group_id:
        enrollment = EnrollmentDB(
            child_id=application.child_id,
            group_id=application.group_id,
            status=EnrollmentStatus.ACTIVE,
            start_date=date.today()
        )
        db.add(enrollment)

    db.commit()

    return RedirectResponse(url="/applications", status_code=303)


@app.get("/applications/{app_id}/reject")
async def reject_application(request: Request, app_id: int, db: Session = Depends(get_db)):
    """Отклонение заявки (админ)"""
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
    """Перевод заявки в лист ожидания (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if application:
        application.status = ApplicationStatus.WAITING_LIST
        db.commit()

    return RedirectResponse(url="/applications", status_code=303)


@app.post("/applications/{app_id}/comment")
async def application_comment(
        request: Request,
        app_id: int,
        admin_comment: str = Form(None),
        db: Session = Depends(get_db)
):
    """Добавление комментария к заявке (админ)"""
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
    """Список запросов на перевод"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")

    query = db.query(TransferRequestDB).order_by(TransferRequestDB.created_at.desc())

    if user["role"] == "coach":
        query = query.filter(TransferRequestDB.coach_id == user["id"])

    transfers = query.all()

    transfers_data = []
    for transfer in transfers:
        transfers_data.append({
            "id": transfer.id,
            "child_name": transfer.child.name if transfer.child else "Unknown",
            "from_group_name": transfer.from_group.name if transfer.from_group else "Unknown",
            "suggested_group_name": transfer.suggested_group.name if transfer.suggested_group else None,
            "coach_name": transfer.coach.name if transfer.coach else "Unknown",
            "comment": transfer.comment,
            "status": transfer.status,
            "created_at": transfer.created_at
        })

    return templates.TemplateResponse(
        name = "transfers.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "transfers": transfers_data
        })


@app.get("/transfers/add", response_class=HTMLResponse)
async def add_transfer_page(request: Request, db: Session = Depends(get_db)):
    """Страница создания запроса на перевод (тренер)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "coach":
        return RedirectResponse(url="/dashboard")

    # Дети в группах тренера
    coach_groups = db.query(GroupDB.id).filter(GroupDB.coach_id == user["id"], GroupDB.is_active == True).all()
    group_ids = [g[0] for g in coach_groups]

    children = db.query(ChildDB).join(EnrollmentDB).filter(
        EnrollmentDB.group_id.in_(group_ids),
        EnrollmentDB.status == EnrollmentStatus.ACTIVE,
        ChildDB.is_active == True
    ).all()

    children_data = []
    for child in children:
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()
        children_data.append({
            "id": child.id,
            "name": child.name,
            "group_name": enrollment.group.name if enrollment else None
        })

    groups = db.query(GroupDB).filter(GroupDB.is_active == True).all()

    return templates.TemplateResponse(
        name = "transfer_form.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "children": children_data,
            "groups": groups
        })


@app.post("/transfers/add")
async def add_transfer(
        request: Request,
        child_id: int = Form(...),
        from_group_id: int = Form(...),
        suggested_group_id: Optional[int] = Form(None),
        comment: Optional[str] = Form(None),
        db: Session = Depends(get_db)
):
    """Создание запроса на перевод (тренер)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "coach":
        return RedirectResponse(url="/dashboard")

    transfer = TransferRequestDB(
        coach_id=user["id"],
        child_id=child_id,
        from_group_id=from_group_id,
        suggested_group_id=suggested_group_id,
        comment=comment,
        status="pending"
    )
    db.add(transfer)
    db.commit()

    return RedirectResponse(url="/transfers", status_code=303)


@app.get("/transfers/{transfer_id}/approve")
async def approve_transfer(request: Request, transfer_id: int, db: Session = Depends(get_db)):
    """Одобрение перевода (админ)"""
    user = get_current_user(request, db)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/dashboard")

    transfer = db.query(TransferRequestDB).filter(TransferRequestDB.id == transfer_id).first()
    if transfer:
        transfer.status = "approved"

        # Обновляем зачисление
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == transfer.child_id,
            EnrollmentDB.group_id == transfer.from_group_id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        if enrollment and transfer.suggested_group_id:
            enrollment.status = EnrollmentStatus.COMPLETED
            enrollment.end_date = date.today()

            new_enrollment = EnrollmentDB(
                child_id=transfer.child_id,
                group_id=transfer.suggested_group_id,
                status=EnrollmentStatus.ACTIVE,
                start_date=date.today()
            )
            db.add(new_enrollment)

            history = TransferHistoryDB(
                child_id=transfer.child_id,
                from_group_id=transfer.from_group_id,
                to_group_id=transfer.suggested_group_id,
                reason=transfer.comment,
                created_by="admin"
            )
            db.add(history)

        db.commit()

    return RedirectResponse(url="/transfers", status_code=303)


@app.get("/transfers/{transfer_id}/reject")
async def reject_transfer(request: Request, transfer_id: int, db: Session = Depends(get_db)):
    """Отклонение перевода (админ)"""
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
    """Профиль родителя"""
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")

    parent = db.query(ParentDB).filter(ParentDB.id == user["id"]).first()

    # Генерируем VK код если нет
    vk_code = parent.vk_link_code
    if not vk_code or (parent.vk_code_expires_at and parent.vk_code_expires_at < datetime.now()):
        vk_code = ''.join(random.choices(string.digits, k=6))
        parent.vk_link_code = vk_code
        parent.vk_code_expires_at = datetime.now() + timedelta(minutes=10)
        db.commit()

    return templates.TemplateResponse(
        name = "profile.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "parent": parent,
            "vk_code": vk_code
        })


@app.post("/profile")
async def update_profile(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        password: Optional[str] = Form(None),
        confirm_password: Optional[str] = Form(None),
        notify_absences: Optional[bool] = Form(False),
        notify_reminders: Optional[bool] = Form(False),
        db: Session = Depends(get_db)
):
    """Обновление профиля родителя"""
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
            return templates.TemplateResponse(
                name = "profile.html", 
                request = request,
                context = {
                    "request": request,
                    "user": user,
                    "parent": parent,
                    "error": "Пароли не совпадают"
                })
        parent.password = password

    db.commit()

    # Обновляем данные в сессии
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        sessions[session_id]["name"] = name
        sessions[session_id]["email"] = email

    return templates.TemplateResponse(
        name = "profile.html", 
        request = request,
        context = {
            "request": request,
            "user": user,
            "parent": parent,
            "success": "Профиль обновлён"
        })


@app.get("/profile/unlink-vk")
async def unlink_vk(request: Request, db: Session = Depends(get_db)):
    """Отвязка VK аккаунта"""
    user = get_current_user(request, db)
    if not user or user["role"] != "parent":
        return RedirectResponse(url="/dashboard")

    parent = db.query(ParentDB).filter(ParentDB.id == user["id"]).first()
    parent.vk_id = None
    parent.is_vk_linked = False

    db.commit()

    return RedirectResponse(url="/profile", status_code=303)


# ========== API ЭНДПОИНТЫ ДЛЯ VK ==========
@app.post("/api/parents/{parent_id}/generate-vk-code")
async def generate_vk_code(parent_id: int, db: Session = Depends(get_db)):
    """Генерация кода для привязки VK"""
    parent = db.query(ParentDB).filter(ParentDB.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    code = ''.join(random.choices(string.digits, k=6))
    parent.vk_link_code = code
    parent.vk_code_expires_at = datetime.now() + timedelta(minutes=10)
    db.commit()

    return {"code": code, "expires_in": 600}


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