# api_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel
from database import (
    get_db, SessionLocal,
    ParentDB, ChildDB, CoachDB, GroupDB, TimeSlotDB,
    EnrollmentDB, ApplicationDB, TrainingDB, AttendanceDB,
    TransferRequestDB, TransferHistoryDB, NotificationDB,
    UserRole, EnrollmentStatus, TrainingStatus, AttendanceStatus,
    ApplicationStatus
)

router = APIRouter(prefix="/api", tags=["API"])


# ========== Pydantic Models ==========

class ChildCreate(BaseModel):
    name: str
    birthdate: date
    class_num: Optional[int] = None
    study_year: Optional[int] = None
    medical_note: Optional[str] = None


class ChildResponse(ChildCreate):
    id: int
    parent_id: Optional[int] = None
    is_active: bool
    group_name: Optional[str] = None

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str
    level: int
    coach_id: Optional[int] = None
    max_capacity: int = 12


class GroupResponse(GroupCreate):
    id: int
    is_active: bool
    coach_name: Optional[str] = None
    current_enrollment: int = 0

    class Config:
        from_attributes = True


class CoachCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: str


class CoachResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    groups_count: int = 0

    class Config:
        from_attributes = True


class TrainingResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    date: date
    start_time: str
    end_time: str
    status: str

    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    id: int
    child_name: Optional[str] = None
    group_name: str
    status: str
    created_at: str
    public_child_name: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceUpdate(BaseModel):
    training_id: int
    child_id: int
    status: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    role: str
    name: str
    email: str


# ========== Auth Endpoints ==========

@router.post("/auth/login", response_model=UserResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Авторизация пользователя"""
    parent = db.query(ParentDB).filter(
        ParentDB.email == request.email,
        ParentDB.password == request.password,
        ParentDB.is_active == True
    ).first()

    if parent:
        return UserResponse(
            id=parent.id,
            role=parent.role.value,
            name=parent.name,
            email=parent.email
        )

    coach = db.query(CoachDB).filter(
        CoachDB.email == request.email,
        CoachDB.password == request.password,
        CoachDB.is_active == True
    ).first()

    if coach:
        return UserResponse(
            id=coach.id,
            role="coach",
            name=coach.name,
            email=coach.email
        )

    if request.email == "admin@pool.ru" and request.password == "admin123":
        return UserResponse(
            id=1,
            role="admin",
            name="Администратор",
            email="admin@pool.ru"
        )

    raise HTTPException(status_code=401, detail="Invalid credentials")


# ========== Dashboard ==========

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Получение статистики для дашборда"""
    children_count = db.query(ChildDB).filter(ChildDB.is_active == True).count()
    groups_count = db.query(GroupDB).filter(GroupDB.is_active == True).count()
    coaches_count = db.query(CoachDB).filter(CoachDB.is_active == True).count()

    today = date.today()
    trainings_this_month = db.query(TrainingDB).filter(
        TrainingDB.date >= date(today.year, today.month, 1),
        TrainingDB.date <= date(today.year, today.month, 28)
    ).count()

    attendances = db.query(AttendanceDB).filter(
        AttendanceDB.status == AttendanceStatus.PRESENT
    ).count()
    total_attendances = db.query(AttendanceDB).count()
    attendance_rate = round((attendances / total_attendances * 100) if total_attendances > 0 else 0)

    pending_applications = db.query(ApplicationDB).filter(
        ApplicationDB.status.in_([ApplicationStatus.NEW, ApplicationStatus.ON_REVIEW])
    ).count()

    return {
        "children": children_count,
        "groups": groups_count,
        "coaches": coaches_count,
        "trainingsThisMonth": trainings_this_month,
        "attendanceRate": attendance_rate,
        "pendingApplications": pending_applications
    }


# ========== Children Endpoints ==========

@router.get("/children", response_model=List[ChildResponse])
def get_children(db: Session = Depends(get_db)):
    """Получение списка всех детей"""
    children = db.query(ChildDB).filter(ChildDB.is_active == True).all()

    result = []
    for child in children:
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        group_name = None
        if enrollment and enrollment.group:
            group_name = enrollment.group.name

        result.append(ChildResponse(
            id=child.id,
            name=child.name,
            birthdate=child.birthdate,
            class_num=child.class_num,
            study_year=child.study_year,
            medical_note=child.medical_note,
            parent_id=child.parent_id,
            is_active=child.is_active,
            group_name=group_name
        ))

    return result


@router.get("/children/{child_id}", response_model=ChildResponse)
def get_child(child_id: int, db: Session = Depends(get_db)):
    """Получение информации о ребёнке"""
    child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    enrollment = db.query(EnrollmentDB).filter(
        EnrollmentDB.child_id == child.id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).first()

    return ChildResponse(
        id=child.id,
        name=child.name,
        birthdate=child.birthdate,
        class_num=child.class_num,
        study_year=child.study_year,
        medical_note=child.medical_note,
        parent_id=child.parent_id,
        is_active=child.is_active,
        group_name=enrollment.group.name if enrollment else None
    )


@router.post("/children", response_model=ChildResponse)
def create_child(child_data: ChildCreate, db: Session = Depends(get_db)):
    """Создание нового ребёнка"""
    child = ChildDB(
        name=child_data.name,
        birthdate=child_data.birthdate,
        class_num=child_data.class_num,
        study_year=child_data.study_year,
        medical_note=child_data.medical_note,
        parent_id=1
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    return ChildResponse(
        id=child.id,
        name=child.name,
        birthdate=child.birthdate,
        class_num=child.class_num,
        study_year=child.study_year,
        medical_note=child.medical_note,
        parent_id=child.parent_id,
        is_active=child.is_active,
        group_name=None
    )


@router.put("/children/{child_id}", response_model=ChildResponse)
def update_child(child_id: int, child_data: ChildCreate, db: Session = Depends(get_db)):
    """Обновление информации о ребёнке"""
    child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    child.name = child_data.name
    child.birthdate = child_data.birthdate
    child.class_num = child_data.class_num
    child.study_year = child_data.study_year
    child.medical_note = child_data.medical_note

    db.commit()
    db.refresh(child)

    return ChildResponse(
        id=child.id,
        name=child.name,
        birthdate=child.birthdate,
        class_num=child.class_num,
        study_year=child.study_year,
        medical_note=child.medical_note,
        parent_id=child.parent_id,
        is_active=child.is_active,
        group_name=None
    )


@router.delete("/children/{child_id}")
def delete_child(child_id: int, db: Session = Depends(get_db)):
    """Удаление ребёнка (мягкое удаление)"""
    child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    child.is_active = False
    db.commit()

    return {"message": "Child deleted"}


# ========== Groups Endpoints ==========

@router.get("/groups", response_model=List[GroupResponse])
def get_groups(db: Session = Depends(get_db)):
    """Получение списка всех групп"""
    groups = db.query(GroupDB).filter(GroupDB.is_active == True).all()

    result = []
    for group in groups:
        current_count = db.query(EnrollmentDB).filter(
            EnrollmentDB.group_id == group.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).count()

        result.append(GroupResponse(
            id=group.id,
            name=group.name,
            level=group.level,
            coach_id=group.coach_id,
            max_capacity=group.max_capacity,
            is_active=group.is_active,
            coach_name=group.coach.name if group.coach else None,
            current_enrollment=current_count
        ))

    return result


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    """Получение информации о группе"""
    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    current_count = db.query(EnrollmentDB).filter(
        EnrollmentDB.group_id == group.id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).count()

    return GroupResponse(
        id=group.id,
        name=group.name,
        level=group.level,
        coach_id=group.coach_id,
        max_capacity=group.max_capacity,
        is_active=group.is_active,
        coach_name=group.coach.name if group.coach else None,
        current_enrollment=current_count
    )


@router.post("/groups", response_model=GroupResponse)
def create_group(group_data: GroupCreate, db: Session = Depends(get_db)):
    """Создание новой группы"""
    group = GroupDB(
        name=group_data.name,
        level=group_data.level,
        coach_id=group_data.coach_id,
        max_capacity=group_data.max_capacity
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    return GroupResponse(
        id=group.id,
        name=group.name,
        level=group.level,
        coach_id=group.coach_id,
        max_capacity=group.max_capacity,
        is_active=group.is_active,
        coach_name=group.coach.name if group.coach else None,
        current_enrollment=0
    )


@router.put("/groups/{group_id}", response_model=GroupResponse)
def update_group(group_id: int, group_data: GroupCreate, db: Session = Depends(get_db)):
    """Обновление информации о группе"""
    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

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
        id=group.id,
        name=group.name,
        level=group.level,
        coach_id=group.coach_id,
        max_capacity=group.max_capacity,
        is_active=group.is_active,
        coach_name=group.coach.name if group.coach else None,
        current_enrollment=current_count
    )


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Удаление группы (мягкое удаление)"""
    group = db.query(GroupDB).filter(GroupDB.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group.is_active = False
    db.commit()

    return {"message": "Group deleted"}


# ========== Coaches Endpoints ==========

@router.get("/coaches", response_model=List[CoachResponse])
def get_coaches(db: Session = Depends(get_db)):
    """Получение списка всех тренеров"""
    coaches = db.query(CoachDB).filter(CoachDB.is_active == True).all()

    result = []
    for coach in coaches:
        groups_count = db.query(GroupDB).filter(
            GroupDB.coach_id == coach.id,
            GroupDB.is_active == True
        ).count()

        result.append(CoachResponse(
            id=coach.id,
            name=coach.name,
            email=coach.email,
            phone=coach.phone,
            is_active=coach.is_active,
            groups_count=groups_count
        ))

    return result


@router.post("/coaches", response_model=CoachResponse)
def create_coach(coach_data: CoachCreate, db: Session = Depends(get_db)):
    """Создание нового тренера"""
    coach = CoachDB(
        name=coach_data.name,
        email=coach_data.email,
        phone=coach_data.phone,
        password=coach_data.password
    )
    db.add(coach)
    db.commit()
    db.refresh(coach)

    return CoachResponse(
        id=coach.id,
        name=coach.name,
        email=coach.email,
        phone=coach.phone,
        is_active=coach.is_active,
        groups_count=0
    )


@router.put("/coaches/{coach_id}", response_model=CoachResponse)
def update_coach(coach_id: int, coach_data: CoachCreate, db: Session = Depends(get_db)):
    """Обновление информации о тренере"""
    coach = db.query(CoachDB).filter(CoachDB.id == coach_id).first()
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found")

    coach.name = coach_data.name
    coach.email = coach_data.email
    coach.phone = coach_data.phone
    if coach_data.password:
        coach.password = coach_data.password

    db.commit()
    db.refresh(coach)

    groups_count = db.query(GroupDB).filter(
        GroupDB.coach_id == coach.id,
        GroupDB.is_active == True
    ).count()

    return CoachResponse(
        id=coach.id,
        name=coach.name,
        email=coach.email,
        phone=coach.phone,
        is_active=coach.is_active,
        groups_count=groups_count
    )


@router.delete("/coaches/{coach_id}")
def delete_coach(coach_id: int, db: Session = Depends(get_db)):
    """Удаление тренера (мягкое удаление)"""
    coach = db.query(CoachDB).filter(CoachDB.id == coach_id).first()
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found")

    coach.is_active = False
    db.commit()

    return {"message": "Coach deleted"}


# ========== Trainings Endpoints ==========

@router.get("/trainings", response_model=List[TrainingResponse])
def get_trainings(group_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    """Получение списка тренировок"""
    query = db.query(TrainingDB)

    if group_id:
        query = query.filter(TrainingDB.group_id == group_id)
    if status:
        query = query.filter(TrainingDB.status == status)

    trainings = query.order_by(TrainingDB.date.desc()).limit(100).all()

    result = []
    for training in trainings:
        result.append(TrainingResponse(
            id=training.id,
            group_id=training.group_id,
            group_name=training.group.name if training.group else "Unknown",
            date=training.date,
            start_time=training.start_time.strftime("%H:%M"),
            end_time=training.end_time.strftime("%H:%M"),
            status=training.status.value if training.status else "unknown"
        ))

    return result


@router.get("/trainings/{training_id}/attendance")
def get_training_attendance(training_id: int, db: Session = Depends(get_db)):
    """Получение посещаемости для тренировки"""
    training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    enrollments = db.query(EnrollmentDB).filter(
        EnrollmentDB.group_id == training.group_id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).all()

    result = []
    for enrollment in enrollments:
        attendance = db.query(AttendanceDB).filter(
            AttendanceDB.training_id == training_id,
            AttendanceDB.child_id == enrollment.child_id
        ).first()

        result.append({
            "child_id": enrollment.child.id,
            "child_name": enrollment.child.name,
            "status": attendance.status.value if attendance else "not_marked",
            "marked_at": attendance.marked_at if attendance else None
        })

    return result


# ========== Attendance Endpoints ==========

@router.post("/attendance")
def mark_attendance(attendance_data: AttendanceUpdate, db: Session = Depends(get_db)):
    """Отметка посещаемости"""
    existing = db.query(AttendanceDB).filter(
        AttendanceDB.training_id == attendance_data.training_id,
        AttendanceDB.child_id == attendance_data.child_id
    ).first()

    if existing:
        existing.status = attendance_data.status
        existing.marked_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    else:
        attendance = AttendanceDB(
            training_id=attendance_data.training_id,
            child_id=attendance_data.child_id,
            status=attendance_data.status,
            marked_by="system"
        )
        db.add(attendance)

    db.commit()

    return {"message": "Attendance marked"}


# ========== Applications Endpoints ==========

@router.get("/applications", response_model=List[ApplicationResponse])
def get_applications(db: Session = Depends(get_db)):
    """Получение списка заявок"""
    applications = db.query(ApplicationDB).order_by(ApplicationDB.created_at.desc()).all()

    result = []
    for app in applications:
        child_name = None
        if app.child:
            child_name = app.child.name
        elif app.public_child_name:
            child_name = app.public_child_name

        result.append(ApplicationResponse(
            id=app.id,
            child_name=child_name,
            group_name=app.group.name if app.group else "Unknown",
            status=app.status.value,
            created_at=app.created_at,
            public_child_name=app.public_child_name
        ))

    return result


@router.post("/applications/{app_id}/approve")
def approve_application(app_id: int, db: Session = Depends(get_db)):
    """Одобрение заявки"""
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.status = ApplicationStatus.APPROVED

    if application.child_id:
        enrollment = EnrollmentDB(
            child_id=application.child_id,
            group_id=application.group_id,
            status=EnrollmentStatus.ACTIVE,
            start_date=date.today()
        )
        db.add(enrollment)

    db.commit()

    return {"message": "Application approved"}


@router.post("/applications/{app_id}/reject")
def reject_application(app_id: int, db: Session = Depends(get_db)):
    """Отклонение заявки"""
    application = db.query(ApplicationDB).filter(ApplicationDB.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.status = ApplicationStatus.REJECTED
    db.commit()

    return {"message": "Application rejected"}


# ========== Transfer Requests Endpoints ==========

@router.get("/transfer-requests")
def get_transfer_requests(db: Session = Depends(get_db)):
    """Получение списка запросов на перевод"""
    requests = db.query(TransferRequestDB).order_by(TransferRequestDB.created_at.desc()).all()

    result = []
    for req in requests:
        result.append({
            "id": req.id,
            "child_name": req.child.name if req.child else "Unknown",
            "from_group_name": req.from_group.name if req.from_group else "Unknown",
            "suggested_group_name": req.suggested_group.name if req.suggested_group else None,
            "status": req.status,
            "comment": req.comment,
            "created_at": req.created_at
        })

    return result


@router.post("/transfer-requests")
def create_transfer_request(request_data: dict, db: Session = Depends(get_db)):
    """Создание запроса на перевод"""
    transfer_request = TransferRequestDB(
        coach_id=1,
        child_id=request_data["child_id"],
        from_group_id=request_data["from_group_id"],
        suggested_group_id=request_data.get("suggested_group_id"),
        comment=request_data.get("comment", ""),
        status="pending"
    )
    db.add(transfer_request)
    db.commit()

    return {"message": "Transfer request created"}


@router.post("/transfer-requests/{req_id}/approve")
def approve_transfer_request(req_id: int, db: Session = Depends(get_db)):
    """Одобрение запроса на перевод"""
    transfer_request = db.query(TransferRequestDB).filter(TransferRequestDB.id == req_id).first()
    if not transfer_request:
        raise HTTPException(status_code=404, detail="Request not found")

    transfer_request.status = "approved"

    enrollment = db.query(EnrollmentDB).filter(
        EnrollmentDB.child_id == transfer_request.child_id,
        EnrollmentDB.group_id == transfer_request.from_group_id,
        EnrollmentDB.status == EnrollmentStatus.ACTIVE
    ).first()

    if enrollment and transfer_request.suggested_group_id:
        enrollment.status = EnrollmentStatus.COMPLETED
        enrollment.end_date = date.today()

        new_enrollment = EnrollmentDB(
            child_id=transfer_request.child_id,
            group_id=transfer_request.suggested_group_id,
            status=EnrollmentStatus.ACTIVE,
            start_date=date.today()
        )
        db.add(new_enrollment)

        history = TransferHistoryDB(
            child_id=transfer_request.child_id,
            from_group_id=transfer_request.from_group_id,
            to_group_id=transfer_request.suggested_group_id,
            reason=transfer_request.comment,
            created_by="admin"
        )
        db.add(history)

    db.commit()

    return {"message": "Transfer request approved"}


@router.post("/transfer-requests/{req_id}/reject")
def reject_transfer_request(req_id: int, db: Session = Depends(get_db)):
    """Отклонение запроса на перевод"""
    transfer_request = db.query(TransferRequestDB).filter(TransferRequestDB.id == req_id).first()
    if not transfer_request:
        raise HTTPException(status_code=404, detail="Request not found")

    transfer_request.status = "rejected"
    db.commit()

    return {"message": "Transfer request rejected"}