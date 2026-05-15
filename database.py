# PoolCRM/database.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, Boolean, Date, Time, DateTime, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import datetime
import enum

# ========== НАСТРОЙКА БД ==========
SQLALCHEMY_DATABASE_URL = "sqlite:///./pool_crm.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ========== ПЕРЕЧИСЛЕНИЯ (ENUMS) ==========
class UserRole(str, enum.Enum):
    PARENT = "parent"
    COACH = "coach"
    ADMIN = "admin"

class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    COMPLETED = "completed"
    WAITING_LIST = "waiting_list"

class TrainingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT_SICK = "absent_sick"
    ABSENT_FAMILY = "absent_family"
    ABSENT_NO_REASON = "absent_no_reason"
    FROZEN_SKIP = "frozen_skip"

class ApplicationStatus(str, enum.Enum):
    PENDING_PARENT_VERIFICATION = "pending_parent_verification"
    NEW = "new"
    ON_REVIEW = "on_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WAITING_LIST = "waiting_list"

# ========== ТАБЛИЦА РОДИТЕЛЕЙ ==========
class ParentDB(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(SQLEnum(UserRole), default=UserRole.PARENT)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String)
    password = Column(String, nullable=False)

    is_vk_linked = Column(Boolean, default=False)
    vk_id = Column(Integer, unique=True, nullable=True)
    vk_link_code = Column(String(6), nullable=True)
    vk_code_expires_at = Column(DateTime, nullable=True)

    notify_absences = Column(Boolean, default=True)
    notify_reminders = Column(Boolean, default=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    children = relationship("ChildDB", back_populates="parent", cascade="all, delete-orphan")
    applications = relationship("ApplicationDB", back_populates="parent")
    notifications = relationship("NotificationDB", back_populates="parent")


# ========== ТАБЛИЦА ДЕТЕЙ ==========
# database.py - в классе ChildDB добавьте:

class ChildDB(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    name = Column(String, nullable=False)
    birthdate = Column(Date, nullable=False)
    class_num = Column(Integer)
    study_year = Column(Integer)
    medical_note = Column(String)
    medical_date = Column(Date)
    is_active = Column(Boolean, default=True)

    parent = relationship("ParentDB", back_populates="children")
    enrollments = relationship("EnrollmentDB", back_populates="child")
    attendances = relationship("AttendanceDB", back_populates="child")
    transfer_history = relationship("TransferHistoryDB", back_populates="child")
    transfer_requests = relationship("TransferRequestDB", back_populates="child")
    applications = relationship("ApplicationDB", back_populates="child")  # <-- ДОБАВИТЬ

# ========== ТАБЛИЦА ТРЕНЕРОВ ==========
class CoachDB(Base):
    __tablename__ = "coaches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    groups = relationship("GroupDB", back_populates="coach")
    transfer_requests = relationship("TransferRequestDB", back_populates="coach")

# ========== ТАБЛИЦА ГРУПП ==========
class GroupDB(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    coach_id = Column(Integer, ForeignKey("coaches.id"))
    max_capacity = Column(Integer, default=12)
    age_tolerance = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    coach = relationship("CoachDB", back_populates="groups")
    time_slots = relationship("TimeSlotDB", back_populates="group", cascade="all, delete-orphan")
    enrollments = relationship("EnrollmentDB", back_populates="group")
    trainings = relationship("TrainingDB", back_populates="group")
    applications = relationship("ApplicationDB", back_populates="group")
    transfer_history_from = relationship("TransferHistoryDB", foreign_keys="TransferHistoryDB.from_group_id", back_populates="from_group")
    transfer_history_to = relationship("TransferHistoryDB", foreign_keys="TransferHistoryDB.to_group_id", back_populates="to_group")
    transfer_requests_from = relationship("TransferRequestDB", foreign_keys="TransferRequestDB.from_group_id", back_populates="from_group")
    transfer_requests_to = relationship("TransferRequestDB", foreign_keys="TransferRequestDB.suggested_group_id", back_populates="suggested_group")

# ========== ТАБЛИЦА ВРЕМЕННЫХ СЛОТОВ ==========
class TimeSlotDB(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    __table_args__ = (
        UniqueConstraint('group_id', 'day_of_week', 'start_time', name='uq_group_day_time'),
    )

    group = relationship("GroupDB", back_populates="time_slots")
    trainings = relationship("TrainingDB", back_populates="time_slot")

# ========== ТАБЛИЦА ТРЕНИРОВОК ==========
class TrainingDB(Base):
    __tablename__ = "trainings"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(SQLEnum(TrainingStatus), default=TrainingStatus.SCHEDULED)

    group = relationship("GroupDB", back_populates="trainings")
    time_slot = relationship("TimeSlotDB", back_populates="trainings")
    attendances = relationship("AttendanceDB", back_populates="training")

# ========== ТАБЛИЦА ЗАЧИСЛЕНИЙ ==========
class EnrollmentDB(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    child = relationship("ChildDB", back_populates="enrollments")
    group = relationship("GroupDB", back_populates="enrollments")

# ========== ТАБЛИЦА ПОСЕЩАЕМОСТИ ==========
class AttendanceDB(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    training_id = Column(Integer, ForeignKey("trainings.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    status = Column(SQLEnum(AttendanceStatus), nullable=False)
    marked_by = Column(String)
    marked_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    training = relationship("TrainingDB", back_populates="attendances")
    child = relationship("ChildDB", back_populates="attendances")

# ========== ТАБЛИЦА ЗАЯВОК ==========
# database.py - найдите класс ApplicationDB и добавьте relationship

class ApplicationDB(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=True)  # Убедитесь, что эта строка есть
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.NEW)
    admin_comment = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    public_parent_name = Column(String)
    public_parent_phone = Column(String)
    public_parent_email = Column(String)
    public_child_name = Column(String)
    public_child_birthdate = Column(Date)
    public_child_class = Column(Integer)
    public_child_study_year = Column(Integer)
    public_child_medical_note = Column(String)
    public_child_medical_date = Column(Date)

    # СВЯЗИ - ДОБАВЬТЕ ЭТИ СТРОКИ:
    parent = relationship("ParentDB", back_populates="applications")
    child = relationship("ChildDB", back_populates="applications")  # <-- ДОБАВИТЬ
    group = relationship("GroupDB", back_populates="applications")

# ========== ТАБЛИЦА ИСТОРИИ ПЕРЕВОДОВ ==========
class TransferHistoryDB(Base):
    __tablename__ = "transfer_history"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    from_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    to_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    reason = Column(String)
    created_by = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    child = relationship("ChildDB", back_populates="transfer_history")
    from_group = relationship("GroupDB", foreign_keys=[from_group_id], back_populates="transfer_history_from")
    to_group = relationship("GroupDB", foreign_keys=[to_group_id], back_populates="transfer_history_to")

# ========== ТАБЛИЦА ЗАПРОСОВ НА ПЕРЕВОД ==========
class TransferRequestDB(Base):
    __tablename__ = "transfer_requests"

    id = Column(Integer, primary_key=True, index=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    from_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    suggested_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    comment = Column(String)
    status = Column(String, default="pending")
    admin_response = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    coach = relationship("CoachDB", back_populates="transfer_requests")
    child = relationship("ChildDB", back_populates="transfer_requests")
    from_group = relationship("GroupDB", foreign_keys=[from_group_id], back_populates="transfer_requests_from")
    suggested_group = relationship("GroupDB", foreign_keys=[suggested_group_id], back_populates="transfer_requests_to")

# ========== ТАБЛИЦА УВЕДОМЛЕНИЙ ==========
class NotificationDB(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    message = Column(String)
    type = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    parent = relationship("ParentDB", back_populates="notifications")

# ========== СОЗДАНИЕ ТАБЛИЦ ==========
Base.metadata.create_all(bind=engine)

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БД ==========
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_by_email(db: Session, email: str, password: str):
    parent = db.query(ParentDB).filter(
        ParentDB.email == email,
        ParentDB.password == password,
        ParentDB.is_active == True
    ).first()
    if parent:
        return {"id": parent.id, "role": parent.role.value, "name": parent.name, "data": parent}

    coach = db.query(CoachDB).filter(
        CoachDB.email == email,
        CoachDB.password == password,
        CoachDB.is_active == True
    ).first()
    if coach:
        return {"id": coach.id, "role": "coach", "name": coach.name, "data": coach}

    return None