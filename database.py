# PoolCRM/database.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, Boolean, Date, Time, DateTime, Enum
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
    ACTIVE = "active"          # ходит
    FROZEN = "frozen"          # заморожен
    COMPLETED = "completed"    # переведён/откреплён
    WAITING_LIST = "waiting_list"  # в листе ожидания


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
    PENDING_PARENT_VERIFICATION = "pending_parent_verification"  # ждёт подтверждения email
    NEW = "new"                      # новая, видна админу
    ON_REVIEW = "on_review"          # на рассмотрении
    APPROVED = "approved"            # одобрена
    REJECTED = "rejected"            # отклонена
    WAITING_LIST = "waiting_list"    # в листе ожидания


# ========== ТАБЛИЦА РОДИТЕЛЕЙ ==========
class ParentDB(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, default="parent")
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String)
    password = Column(String, nullable=False)  # в реальном проекте — хэш

    # VK
    is_vk_linked = Column(Boolean, default=False)
    vk_id = Column(Integer, unique=True, nullable=True)
    vk_link_code = Column(String(6), nullable=True)
    vk_code_expires_at = Column(DateTime, nullable=True)

    # Настройки уведомлений
    notify_absences = Column(Boolean, default=True)
    notify_reminders = Column(Boolean, default=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    # Связи
    children = relationship("ChildDB", back_populates="parent", cascade="all, delete-orphan")
    applications = relationship("ApplicationDB", back_populates="parent")


# ========== ТАБЛИЦА ДЕТЕЙ ==========
class ChildDB(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    name = Column(String, nullable=False)
    birthdate = Column(Date, nullable=False)
    class_num = Column(Integer)             # класс в школе
    study_year = Column(Integer)            # год обучения плаванию (уровень)
    medical_note = Column(String)           # данные мед. справки
    medical_date = Column(Date)             # дата выдачи справки
    is_active = Column(Boolean, default=True)

    # Связи
    parent = relationship("ParentDB", back_populates="children")
    enrollments = relationship("EnrollmentDB", back_populates="child")
    attendances = relationship("AttendanceDB", back_populates="child")


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

    # Связи
    groups = relationship("GroupDB", back_populates="coach")
    child_notes = relationship("CoachNoteDB", back_populates="coach")


# ========== ТАБЛИЦА ГРУПП ==========
class GroupDB(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False)         # год обучения
    coach_id = Column(Integer, ForeignKey("coaches.id"))
    max_capacity = Column(Integer, default=12)
    age_tolerance = Column(Float, default=1.0)      # ± лет от нормы
    is_active = Column(Boolean, default=True)
    note = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    # Связи
    coach = relationship("CoachDB", back_populates="groups")
    time_slots = relationship("TimeSlotDB", back_populates="group", cascade="all, delete-orphan")
    enrollments = relationship("EnrollmentDB", back_populates="group")
    trainings = relationship("TrainingDB", back_populates="group")
    applications = relationship("ApplicationDB", back_populates="group")


# ========== ТАБЛИЦА ВРЕМЕННЫХ СЛОТОВ ==========
class TimeSlotDB(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)   # 0-6 (Пн-Вс)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # Связи
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
    status = Column(Enum(TrainingStatus), default=TrainingStatus.SCHEDULED)

    # Связи
    group = relationship("GroupDB", back_populates="trainings")
    time_slot = relationship("TimeSlotDB", back_populates="trainings")
    attendances = relationship("AttendanceDB", back_populates="training")


# ========== ТАБЛИЦА ЗАЧИСЛЕНИЙ ==========
class EnrollmentDB(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    # Связи
    child = relationship("ChildDB", back_populates="enrollments")
    group = relationship("GroupDB", back_populates="enrollments")


# ========== ТАБЛИЦА ПОСЕЩАЕМОСТИ ==========
class AttendanceDB(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    training_id = Column(Integer, ForeignKey("trainings.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    status = Column(Enum(AttendanceStatus), nullable=False)
    comment = Column(String)
    marked_by = Column(String)  # кто поставил отметку
    marked_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    # Связи
    training = relationship("TrainingDB", back_populates="attendances")
    child = relationship("ChildDB", back_populates="attendances")


# ========== ТАБЛИЦА ЗАЯВОК ==========
class ApplicationDB(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)  # NULL для публичных заявок
    child_id = Column(Integer, ForeignKey("children.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.NEW)
    admin_comment = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    # Для публичных заявок (родитель без аккаунта)
    public_parent_name = Column(String)
    public_parent_phone = Column(String)
    public_parent_email = Column(String)
    public_child_name = Column(String)
    public_child_birthdate = Column(Date)
    public_child_class = Column(Integer)
    public_child_study_year = Column(Integer)
    public_child_medical_note = Column(String)
    public_child_medical_date = Column(Date)

    # Связи
    parent = relationship("ParentDB", back_populates="applications")
    group = relationship("GroupDB", back_populates="applications")


# ========== ТАБЛИЦА ЗАМЕТОК ТРЕНЕРА ==========
class CoachNoteDB(Base):
    __tablename__ = "coach_notes"

    id = Column(Integer, primary_key=True, index=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    note = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))
    updated_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

    coach = relationship("CoachDB", back_populates="child_notes")


# ========== ТАБЛИЦА ИСТОРИИ ПЕРЕВОДОВ ==========
class TransferHistoryDB(Base):
    __tablename__ = "transfer_history"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    from_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    to_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    reason = Column(String)
    created_by = Column(String)  # кто перевёл
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))


# ========== ТАБЛИЦА ЗАПРОСОВ НА ПЕРЕВОД (от тренера) ==========
class TransferRequestDB(Base):
    __tablename__ = "transfer_requests"

    id = Column(Integer, primary_key=True, index=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    from_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    suggested_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    comment = Column(String)
    status = Column(String, default="pending")  # pending/approved/rejected
    admin_response = Column(String)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))


# ========== ТАБЛИЦА УВЕДОМЛЕНИЙ ==========
class NotificationDB(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    message = Column(String)
    type = Column(String)  # absence_warning/reminder/application_status/system
    is_read = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))


# ========== СОЗДАНИЕ ТАБЛИЦ ==========
Base.metadata.create_all(bind=engine)


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БД ==========

def get_db():
    """Возвращает сессию базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_users(db: Session):
    """Создаёт тестовых пользователей для демонстрации"""
    if db.query(ParentDB).count() > 0:
        return

    # Администратор
    admin = ParentDB(
        name="Администратор",
        email="admin@pool.ru",
        phone="+79000000001",
        password="admin123",
        role="admin"
    )
    db.add(admin)

    # Родитель
    parent = ParentDB(
        name="Мария Иванова",
        email="parent@pool.ru",
        phone="+79000000002",
        password="parent123",
        role="parent"
    )
    db.add(parent)
    db.flush()

    # Ребёнок
    child = ChildDB(
        parent_id=parent.id,
        name="Петя Иванов",
        birthdate=datetime(2018, 5, 15).date(),
        class_num=1,
        study_year=1,
        medical_note="Справка №123",
        medical_date=datetime(2025, 9, 1).date()
    )
    db.add(child)

    # Тренер
    coach = CoachDB(
        name="Иван Петрович",
        email="coach@pool.ru",
        phone="+79000000003",
        password="coach123"
    )
    db.add(coach)
    db.flush()

    # Группа
    group = GroupDB(
        name="Начинающие 6-7 лет",
        level=1,
        coach_id=coach.id,
        max_capacity=10
    )
    db.add(group)
    db.flush()

    # TimeSlot
    slot = TimeSlotDB(
        group_id=group.id,
        day_of_week=0,
        start_time=datetime.strptime("18:00", "%H:%M").time(),
        end_time=datetime.strptime("19:00", "%H:%M").time()
    )
    db.add(slot)

    db.commit()
    print("✅ Созданы тестовые пользователи:")
    print("   Админ: admin@pool.ru / admin123")
    print("   Родитель: parent@pool.ru / parent123")
    print("   Тренер: coach@pool.ru / coach123")


def get_user_by_email(db: Session, email: str, password: str):
    """Проверяет логин-пароль, возвращает пользователя любой роли или None"""
    # Ищем среди родителей и админов
    parent = db.query(ParentDB).filter(
        ParentDB.email == email,
        ParentDB.password == password,
        ParentDB.is_active == True
    ).first()
    if parent:
        return {"id": parent.id, "role": parent.role, "name": parent.name, "data": parent}

    # Ищем среди тренеров
    coach = db.query(CoachDB).filter(
        CoachDB.email == email,
        CoachDB.password == password,
        CoachDB.is_active == True
    ).first()
    if coach:
        return {"id": coach.id, "role": "coach", "name": coach.name, "data": coach}

    return None
