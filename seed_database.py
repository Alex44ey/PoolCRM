# seed_database.py
"""
Скрипт для заполнения базы данных тестовыми данными
Запуск: python seed_database.py
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import (
    SessionLocal, engine, Base,
    ParentDB, ChildDB, CoachDB, GroupDB, TimeSlotDB,
    EnrollmentDB, ApplicationDB, TrainingDB, AttendanceDB,
    UserRole, EnrollmentStatus, TrainingStatus, AttendanceStatus,
    ApplicationStatus
)


# ========== ТЕСТОВЫЕ ДАННЫЕ ==========
def create_test_parents(db: Session):
    """Создание тестовых родителей"""
    parents = [
        {
            "name": "Иванова Мария Петровна",
            "email": "maria@example.com",
            "phone": "+79161234567",
            "password": "parent123",
            "role": UserRole.PARENT,
            "is_vk_linked": True,
            "vk_id": 123456789,
            "notify_absences": True,
            "notify_reminders": True
        },
        {
            "name": "Петров Сергей Иванович",
            "email": "sergey@example.com",
            "phone": "+79169876543",
            "password": "parent123",
            "role": UserRole.PARENT,
            "is_vk_linked": False,
            "vk_id": None,
            "notify_absences": True,
            "notify_reminders": False
        },
        {
            "name": "Сидорова Анна Владимировна",
            "email": "anna@example.com",
            "phone": "+79165553322",
            "password": "parent123",
            "role": UserRole.PARENT,
            "is_vk_linked": True,
            "vk_id": 987654321,
            "notify_absences": True,
            "notify_reminders": True
        },
        {
            "name": "Администратор Системы",
            "email": "admin@pool.ru",
            "phone": "+79001234567",
            "password": "admin123",
            "role": UserRole.ADMIN,
            "is_vk_linked": False,
            "vk_id": None,
            "notify_absences": False,
            "notify_reminders": False
        }
    ]

    created_parents = []
    for parent_data in parents:
        existing = db.query(ParentDB).filter(ParentDB.email == parent_data["email"]).first()
        if not existing:
            parent = ParentDB(**parent_data)
            db.add(parent)
            db.flush()
            created_parents.append(parent)
            print(f"  ✅ Создан родитель: {parent.name} ({parent.email})")
        else:
            created_parents.append(existing)
            print(f"  ⏭️ Родитель уже существует: {existing.name}")

    return created_parents

def create_test_children(db: Session, parents):
    """Создание тестовых детей"""
    children_data = [
        # Дети Марии Ивановой
        {"parent_id": parents[0].id, "name": "Иванов Артём", "birthdate": datetime(2016, 5, 10).date(),
         "class_num": 3, "study_year": 2, "medical_note": "Справка №123 от 01.09.2025",
         "medical_date": datetime(2025, 9, 1).date()},
        {"parent_id": parents[0].id, "name": "Иванова София", "birthdate": datetime(2018, 8, 15).date(),
         "class_num": 1, "study_year": 1, "medical_note": "Справка №124 от 01.09.2025",
         "medical_date": datetime(2025, 9, 1).date()},

        # Дети Сергея Петрова
        {"parent_id": parents[1].id, "name": "Петров Максим", "birthdate": datetime(2015, 3, 20).date(),
         "class_num": 4, "study_year": 3, "medical_note": "Справка №125 от 01.09.2024",
         "medical_date": datetime(2024, 9, 1).date()},  # просрочена

        # Дети Анны Сидоровой
        {"parent_id": parents[2].id, "name": "Сидоров Дмитрий", "birthdate": datetime(2017, 7, 25).date(),
         "class_num": 2, "study_year": 2, "medical_note": "Справка №126 от 01.09.2025",
         "medical_date": datetime(2025, 9, 1).date()},
        {"parent_id": parents[2].id, "name": "Сидорова Екатерина", "birthdate": datetime(2019, 11, 5).date(),
         "class_num": 0, "study_year": 1, "medical_note": "Справка №127 от 01.09.2025",
         "medical_date": datetime(2025, 9, 1).date()},
    ]

    created_children = []
    for child_data in children_data:
        child = ChildDB(**child_data)
        db.add(child)
        db.flush()
        created_children.append(child)
        print(f"  ✅ Создан ребёнок: {child.name} (родитель: {parents[child.parent_id - 1].name})")

    return created_children

def create_test_coaches(db: Session):
    """Создание тестовых тренеров"""
    coaches_data = [
        {"name": "Кузнецов Иван Петрович", "email": "ivan.coach@pool.ru", "phone": "+79161112233",
         "password": "coach123"},
        {"name": "Смирнова Елена Александровна", "email": "elena.coach@pool.ru", "phone": "+79164445566",
         "password": "coach123"},
        {"name": "Михайлов Алексей Владимирович", "email": "alexey.coach@pool.ru", "phone": "+79167778899",
         "password": "coach123"},
    ]

    created_coaches = []
    for coach_data in coaches_data:
        existing = db.query(CoachDB).filter(CoachDB.email == coach_data["email"]).first()
        if not existing:
            coach = CoachDB(**coach_data)
            db.add(coach)
            db.flush()
            created_coaches.append(coach)
            print(f"  ✅ Создан тренер: {coach.name} ({coach.email})")
        else:
            created_coaches.append(existing)
            print(f"  ⏭️ Тренер уже существует: {existing.name}")

    return created_coaches

def create_test_groups(db: Session, coaches):
    """Создание тестовых групп"""
    groups_data = [
        {"name": "Начинающие (6-7 лет)", "level": 1, "coach_id": coaches[0].id, "max_capacity": 12,
         "age_tolerance": 1.0},
        {"name": "Продолжающие (8-9 лет)", "level": 2, "coach_id": coaches[0].id, "max_capacity": 12,
         "age_tolerance": 1.5},
        {"name": "Спортивная группа (10-11 лет)", "level": 3, "coach_id": coaches[1].id, "max_capacity": 10,
         "age_tolerance": 0.5},
        {"name": "Начинающие взрослые", "level": 1, "coach_id": coaches[2].id, "max_capacity": 8, "age_tolerance": 5.0},
        {"name": "Малыши (5-6 лет)", "level": 0, "coach_id": coaches[2].id, "max_capacity": 10, "age_tolerance": 0.5},
    ]

    created_groups = []
    for group_data in groups_data:
        existing = db.query(GroupDB).filter(GroupDB.name == group_data["name"]).first()
        if not existing:
            group = GroupDB(**group_data)
            db.add(group)
            db.flush()
            created_groups.append(group)
            print(f"  ✅ Создана группа: {group.name} (тренер: {group.coach.name})")
        else:
            created_groups.append(existing)
            print(f"  ⏭️ Группа уже существует: {existing.name}")

    return created_groups

def create_test_time_slots(db: Session, groups):
    """Создание расписания для групп"""
    slots_data = [
        # Группа "Начинающие (6-7 лет)"
        {"group_id": groups[0].id, "day_of_week": 0, "start_time": datetime.strptime("17:00", "%H:%M").time(),
         "end_time": datetime.strptime("18:00", "%H:%M").time()},  # Пн
        {"group_id": groups[0].id, "day_of_week": 2, "start_time": datetime.strptime("17:00", "%H:%M").time(),
         "end_time": datetime.strptime("18:00", "%H:%M").time()},  # Ср
        {"group_id": groups[0].id, "day_of_week": 5, "start_time": datetime.strptime("10:00", "%H:%M").time(),
         "end_time": datetime.strptime("11:00", "%H:%M").time()},  # Сб

        # Группа "Продолжающие (8-9 лет)"
        {"group_id": groups[1].id, "day_of_week": 1, "start_time": datetime.strptime("18:00", "%H:%M").time(),
         "end_time": datetime.strptime("19:00", "%H:%M").time()},  # Вт
        {"group_id": groups[1].id, "day_of_week": 3, "start_time": datetime.strptime("18:00", "%H:%M").time(),
         "end_time": datetime.strptime("19:00", "%H:%M").time()},  # Чт

        # Группа "Спортивная группа (10-11 лет)"
        {"group_id": groups[2].id, "day_of_week": 1, "start_time": datetime.strptime("19:00", "%H:%M").time(),
         "end_time": datetime.strptime("20:30", "%H:%M").time()},  # Вт
        {"group_id": groups[2].id, "day_of_week": 4, "start_time": datetime.strptime("19:00", "%H:%M").time(),
         "end_time": datetime.strptime("20:30", "%H:%M").time()},  # Пт

        # Группа "Начинающие взрослые"
        {"group_id": groups[3].id, "day_of_week": 0, "start_time": datetime.strptime("20:00", "%H:%M").time(),
         "end_time": datetime.strptime("21:00", "%H:%M").time()},  # Пн
        {"group_id": groups[3].id, "day_of_week": 3, "start_time": datetime.strptime("20:00", "%H:%M").time(),
         "end_time": datetime.strptime("21:00", "%H:%M").time()},  # Чт

        # Группа "Малыши (5-6 лет)"
        {"group_id": groups[4].id, "day_of_week": 5, "start_time": datetime.strptime("10:00", "%H:%M").time(),
         "end_time": datetime.strptime("10:45", "%H:%M").time()},  # Сб
    ]

    created_slots = []
    for slot_data in slots_data:
        existing = db.query(TimeSlotDB).filter(
            TimeSlotDB.group_id == slot_data["group_id"],
            TimeSlotDB.day_of_week == slot_data["day_of_week"],
            TimeSlotDB.start_time == slot_data["start_time"]
        ).first()

        if not existing:
            slot = TimeSlotDB(**slot_data)
            db.add(slot)
            db.flush()
            created_slots.append(slot)
            days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            print(f"  ✅ Создан слот: {days[slot.day_of_week]} {slot.start_time}-{slot.end_time} для группы {slot.group.name}")
        else:
            created_slots.append(existing)

    return created_slots

def create_test_trainings(db: Session, groups, time_slots):
    """Создание тестовых тренировок за последние 30 дней и следующие 30 дней"""
    today = datetime.now().date()
    created_trainings = []
    training_count = 0

    for time_slot in time_slots:
        # Создаём тренировки за последние 30 дней и на следующие 30 дней
        for days_offset in range(-30, 31):
            training_date = today + timedelta(days=days_offset)
            # Проверяем, совпадает ли день недели
            if training_date.weekday() == time_slot.day_of_week:
                # Определяем статус тренировки
                if training_date < today:
                    status = TrainingStatus.COMPLETED
                elif training_date == today:
                    status = TrainingStatus.SCHEDULED
                else:
                    status = TrainingStatus.SCHEDULED

                # Для демонстрации отменённой тренировки
                if training_date == today - timedelta(days=7) and training_count % 5 == 0:
                    status = TrainingStatus.CANCELLED

                training = TrainingDB(
                    group_id=time_slot.group_id,
                    time_slot_id=time_slot.id,
                    date=training_date,
                    start_time=time_slot.start_time,
                    end_time=time_slot.end_time,
                    status=status
                )
                db.add(training)
                created_trainings.append(training)
                training_count += 1

    db.flush()
    print(f"  ✅ Создано {len(created_trainings)} тренировок")
    return created_trainings

def create_test_enrollments(db: Session, children, groups):
    """Создание зачислений детей в группы"""
    enrollments_data = [
        # Артём Иванов в "Начинающие (6-7 лет)"
        {"child_id": children[0].id, "group_id": groups[0].id, "status": EnrollmentStatus.ACTIVE,
         "start_date": datetime(2025, 9, 1).date()},

        # София Иванова в "Малыши (5-6 лет)"
        {"child_id": children[1].id, "group_id": groups[4].id, "status": EnrollmentStatus.ACTIVE,
         "start_date": datetime(2025, 9, 1).date()},

        # Максим Петров в "Продолжающие (8-9 лет)"
        {"child_id": children[2].id, "group_id": groups[1].id, "status": EnrollmentStatus.ACTIVE,
         "start_date": datetime(2025, 9, 1).date()},

        # Дмитрий Сидоров в "Продолжающие (8-9 лет)"
        {"child_id": children[3].id, "group_id": groups[1].id, "status": EnrollmentStatus.ACTIVE,
         "start_date": datetime(2025, 9, 1).date()},

        # Екатерина Сидорова в "Начинающие (6-7 лет)"
        {"child_id": children[4].id, "group_id": groups[0].id, "status": EnrollmentStatus.ACTIVE,
         "start_date": datetime(2025, 9, 1).date()},

        # Замороженный ученик (Артём Иванов был заморожен в другой группе)
        {"child_id": children[0].id, "group_id": groups[1].id, "status": EnrollmentStatus.FROZEN,
         "start_date": datetime(2025, 1, 15).date(), "end_date": datetime(2025, 3, 15).date()},
    ]

    created_enrollments = []
    for enrollment_data in enrollments_data:
        enrollment = EnrollmentDB(**enrollment_data)
        db.add(enrollment)
        db.flush()
        created_enrollments.append(enrollment)
        child = next(c for c in children if c.id == enrollment.child_id)
        group = next(g for g in groups if g.id == enrollment.group_id)
        print(f"  ✅ Создано зачисление: {child.name} -> {group.name} ({enrollment.status.value})")

    return created_enrollments

def create_test_attendances(db: Session, trainings, children, enrollments):
    """Создание тестовых отметок посещаемости"""
    import random

    created_attendances = []

    # Создаём словарь активных зачислений для быстрого доступа
    active_enrollments = {}
    for enrollment in enrollments:
        if enrollment.status == EnrollmentStatus.ACTIVE:
            active_enrollments[enrollment.child_id] = enrollment.group_id

    for training in trainings:
        # Пропускаем отменённые тренировки
        if training.status == TrainingStatus.CANCELLED:
            continue

        # Находим всех детей, которые были активны в этой группе на дату тренировки
        for child in children:
            if child.id not in active_enrollments:
                continue

            # Проверяем, был ли ребёнок в этой группе на момент тренировки
            child_enrollment = next(
                (e for e in enrollments if e.child_id == child.id and
                 e.group_id == training.group_id and
                 e.start_date <= training.date and
                 (e.end_date is None or e.end_date >= training.date)),
                None
            )

            if not child_enrollment:
                continue

            # Если заморожен - пропускаем
            if child_enrollment.status == EnrollmentStatus.FROZEN:
                continue

            # Для прошедших тренировок (completed) создаём отметки
            if training.status == TrainingStatus.COMPLETED:
                # Имитируем разные паттерны посещаемости
                child_name = child.name

                if child_name == "Иванов Артём":
                    # Хорошая посещаемость
                    status = random.choices(
                        [AttendanceStatus.PRESENT, AttendanceStatus.ABSENT_SICK],
                        weights=[90, 10]
                    )[0]
                elif child_name == "Петров Максим":
                    # Часто пропускает без причины
                    status = random.choices(
                        [AttendanceStatus.PRESENT, AttendanceStatus.ABSENT_NO_REASON],
                        weights=[60, 40]
                    )[0]
                elif child_name == "Сидоров Дмитрий":
                    # Иногда болеет
                    status = random.choices(
                        [AttendanceStatus.PRESENT, AttendanceStatus.ABSENT_SICK],
                        weights=[85, 15]
                    )[0]
                else:
                    # Стандартная посещаемость
                    status = random.choices(
                        [AttendanceStatus.PRESENT, AttendanceStatus.ABSENT_SICK,
                         AttendanceStatus.ABSENT_FAMILY, AttendanceStatus.ABSENT_NO_REASON],
                        weights=[70, 15, 10, 5]
                    )[0]

                attendance = AttendanceDB(
                    training_id=training.id,
                    child_id=child.id,
                    status=status,
                    marked_by="Тренер (авто)"
                )
                db.add(attendance)
                created_attendances.append(attendance)

    db.flush()
    print(f"  ✅ Создано {len(created_attendances)} записей посещаемости")
    return created_attendances

def create_test_applications(db: Session, parents, children, groups):
    """Создание тестовых заявок"""
    applications_data = [
        # Одобренная заявка
        {"parent_id": parents[0].id, "child_id": children[0].id, "group_id": groups[0].id,
         "status": ApplicationStatus.APPROVED, "admin_comment": "Одобрено"},

        # На рассмотрении
        {"parent_id": parents[1].id, "child_id": children[2].id, "group_id": groups[2].id,
         "status": ApplicationStatus.ON_REVIEW, "admin_comment": None},

        # Отклонённая
        {"parent_id": parents[2].id, "child_id": children[3].id, "group_id": groups[3].id,
         "status": ApplicationStatus.REJECTED, "admin_comment": "Нет мест"},

        # В листе ожидания
        {"parent_id": parents[2].id, "child_id": children[4].id, "group_id": groups[0].id,
         "status": ApplicationStatus.WAITING_LIST, "admin_comment": "Группа переполнена"},

        # Публичная заявка (без родительского аккаунта)
        {"parent_id": None, "child_id": None, "group_id": groups[4].id,
         "status": ApplicationStatus.NEW,
         "public_parent_name": "Новиков Олег",
         "public_parent_phone": "+79169998877",
         "public_parent_email": "novikov@example.com",
         "public_child_name": "Новиков Андрей",
         "public_child_birthdate": datetime(2017, 4, 10).date(),
         "public_child_class": 2,
         "public_child_study_year": 1,
         "public_child_medical_note": "Справка №128",
         "public_child_medical_date": datetime(2025, 9, 1).date()},
    ]

    created_applications = []
    for app_data in applications_data:
        application = ApplicationDB(**app_data)
        db.add(application)
        db.flush()
        created_applications.append(application)
        print(f"  ✅ Создана заявка #{application.id}: статус {application.status.value}")

    return created_applications


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def seed_database():
    """Главная функция для заполнения БД тестовыми данными"""
    print("\n" + "=" * 60)
    print("🌊 НАЧАЛО ЗАПОЛНЕНИЯ БАЗЫ ДАННЫХ POOL CRM")
    print("=" * 60 + "\n")

    # Создаём сессию
    db = SessionLocal()

    try:
        # Создаём таблицы (если их нет)
        print("📦 Проверка/создание таблиц...")
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы готовы\n")

        # 1. Родители
        print("👨‍👩‍👧 Создание родителей:")
        parents = create_test_parents(db)
        print()

        # 2. Дети
        print("👶 Создание детей:")
        children = create_test_children(db, parents)
        print()

        # 3. Тренеры
        print("🏊‍♂️ Создание тренеров:")
        coaches = create_test_coaches(db)
        print()

        # 4. Группы
        print("👥 Создание групп:")
        groups = create_test_groups(db, coaches)
        print()

        # 5. Расписание (TimeSlot)
        print("📅 Создание расписания:")
        time_slots = create_test_time_slots(db, groups)
        print()

        # 6. Тренировки
        print("🏊 Создание тренировок:")
        trainings = create_test_trainings(db, groups, time_slots)
        print()

        # 7. Зачисления
        print("📝 Создание зачислений:")
        enrollments = create_test_enrollments(db, children, groups)
        print()

        # 8. Посещаемость
        print("📊 Создание посещаемости:")
        attendances = create_test_attendances(db, trainings, children, enrollments)
        print()

        # 9. Заявки
        print("📋 Создание заявок:")
        applications = create_test_applications(db, parents, children, groups)
        print()

        # Сохраняем все изменения
        db.commit()

        print("=" * 60)
        print("🎉 БАЗА ДАННЫХ УСПЕШНО ЗАПОЛНЕНА!")
        print("=" * 60)

        # Вывод статистики
        print("\n📊 СТАТИСТИКА:")
        print(f"   👨‍👩‍👧 Родителей: {len(parents)}")
        print(f"   👶 Детей: {len(children)}")
        print(f"   🏊‍♂️ Тренеров: {len(coaches)}")
        print(f"   👥 Групп: {len(groups)}")
        print(f"   📅 Слотов расписания: {len(time_slots)}")
        print(f"   🏊 Тренировок: {len(trainings)}")
        print(f"   📝 Зачислений: {len(enrollments)}")
        print(f"   📊 Записей посещаемости: {len(attendances)}")
        print(f"   📋 Заявок: {len(applications)}")

        print("\n🔑 ТЕСТОВЫЕ УЧЁТНЫЕ ЗАПИСИ:")
        print("   👨‍👩‍👧 Родители:")
        print("      maria@example.com / parent123 (Мария Иванова)")
        print("      sergey@example.com / parent123 (Сергей Петров)")
        print("      anna@example.com / parent123 (Анна Сидорова)")
        print("   🏊‍♂️ Тренеры:")
        print("      ivan.coach@pool.ru / coach123 (Иван Кузнецов)")
        print("      elena.coach@pool.ru / coach123 (Елена Смирнова)")
        print("      alexey.coach@pool.ru / coach123 (Алексей Михайлов)")
        print("   👑 Администратор:")
        print("      admin@pool.ru / admin123")

        print("\n📈 ПРИМЕРЫ ДАННЫХ:")
        print("   ✅ Артём Иванов (хорошая посещаемость) - группа 'Начинающие (6-7 лет)'")
        print("   ✅ Максим Петров (часто пропускает) - группа 'Продолжающие (8-9 лет)'")
        print("   ✅ София Иванова - группа 'Малыши (5-6 лет)'")
        print("   ⭐ Заморожен: Артём Иванов (январь-март 2025)")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# ========== ЗАПУСК ==========
if __name__ == "__main__":
    seed_database()