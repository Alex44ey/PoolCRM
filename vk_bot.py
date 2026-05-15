# vk_bot.py
"""
VK бот для уведомлений о посещаемости
"""

import random
import string
from datetime import datetime, timedelta
from threading import Thread
import time
import requests

from sqlalchemy.orm import Session

from database import (
    ParentDB, ChildDB, AttendanceDB, TrainingDB,
    AttendanceStatus
)

# ========== НАСТРОЙКИ VK ==========
# ВСТАВЬТЕ ВАШ ТОКЕН ПОЛЬЗОВАТЕЛЯ!
# Получить токен можно здесь: https://vkhost.github.io/
# Выберите разрешения: messages, offline
VK_USER_TOKEN = "vk1.a.pyfkac7ghRZAJ8sQPjOdAAjAEJaf2Gp3MRPCNypYLE9nVs7y6y43bulnFpyzVTRJGp06Ul5CmHiOHcld3JjeS53txVob2elSdq1YMrZOibj324gqmUz6exQ6t4RVgn4fm91o-zW27JVF_e02ZvtQ03T5dH2mMs_BR691yEZxxgCbxwS81VW8aPWU8LfLTfvzkoBNOYJMWMQSbWLPR6U4Tw"  # ЗАМЕНИТЕ НА ВАШ ТОКЕН!

# ID вашего сообщества (если есть)
VK_GROUP_ID = 0

# Включить/выключить бота
VK_ENABLED = False  # Поставьте True после настройки токена

VK_API_VERSION = "5.131"


def send_vk_message(user_vk_id: int, message: str) -> bool:
    """Отправка сообщения пользователю VK"""
    if not VK_ENABLED:
        print(f"[VK] Бот отключён. Сообщение не отправлено: {message[:50]}...")
        return False

    if not VK_USER_TOKEN or VK_USER_TOKEN == "YOUR_VK_TOKEN_HERE":
        print("[VK] Токен не настроен!")
        return False

    try:
        url = "https://api.vk.com/method/messages.send"
        params = {
            "user_id": user_vk_id,
            "random_id": int(time.time() * 1000),
            "message": message,
            "access_token": VK_USER_TOKEN,
            "v": VK_API_VERSION
        }

        if VK_GROUP_ID:
            params["group_id"] = VK_GROUP_ID

        response = requests.post(url, params=params)
        data = response.json()

        if "error" in data:
            print(f"[VK] Ошибка: {data['error']}")
            return False

        print(f"[VK] Сообщение отправлено пользователю {user_vk_id}")
        return True

    except Exception as e:
        print(f"[VK] Ошибка: {e}")
        return False


def send_attendance_notification_vk(
        child_id: int,
        training_id: int,
        status: str,
        db: Session
):
    """
    Отправка уведомления родителю о посещаемости
    Вызывается из api_routes при отметке посещаемости
    """
    if not VK_ENABLED:
        return

    try:
        child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
        if not child or not child.parent:
            return

        parent = child.parent

        # Проверяем, включены ли уведомления
        if not parent.notify_reminders:
            return

        # Проверяем, привязан ли VK
        if not parent.is_vk_linked or not parent.vk_id:
            return
            # Получаем информацию о тренировке
        training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
        if not training:
            return

        group_name = training.group.name if training.group else "Неизвестная группа"

        # Формируем сообщение в зависимости от статуса
        if status == "present":
            message = (
                f"✅ {child.name} присутствовал на тренировке!\n"
                f"📅 {training.date.strftime('%d.%m.%Y')}\n"
                f"👥 Группа: {group_name}\n\n"
                f"🏊‍♂️ Хорошая работа!"
            )
        elif status == "absent_sick":
            message = (
                f"❌ {child.name} отсутствовал на тренировке по болезни\n"
                f"📅 {training.date.strftime('%d.%m.%Y')}\n"
                f"👥 Группа: {group_name}\n\n"
                f"🌡️ Желаем скорейшего выздоровления!"
            )
        elif status == "absent_family":
            message = (
                f"❌ {child.name} отсутствовал на тренировке\n"
                f"📅 {training.date.strftime('%d.%m.%Y')}\n"
                f"👥 Группа: {group_name}\n\n"
                f"📌 Причина: семейные обстоятельства"
            )
        elif status == "absent_no_reason":
            message = (
                f"⚠️ {child.name} отсутствовал на тренировке БЕЗ УВАЖИТЕЛЬНОЙ ПРИЧИНЫ!\n"
                f"📅 {training.date.strftime('%d.%m.%Y')}\n"
                f"👥 Группа: {group_name}\n\n"
                f"Пожалуйста, сообщите тренеру о причинах пропуска."
            )
        else:
            return

        send_vk_message(parent.vk_id, message)

    except Exception as e:
        print(f"[VK] Ошибка отправки уведомления: {e}")


def process_vk_message(user_vk_id: int, message_text: str, db: Session) -> str:
    """Обработка входящего сообщения от пользователя (команды боту)"""
    message_text = message_text.lower().strip()

    # Поиск родителя по VK ID
    parent = db.query(ParentDB).filter(
        ParentDB.vk_id == user_vk_id,
        ParentDB.is_active == True
    ).first()

    if not parent:
        if message_text.startswith("привязать"):
            parts = message_text.split()
            if len(parts) >= 2:
                code = parts[1]
                return link_parent_by_code(user_vk_id, code, db)
            else:
                return (
                    "🔗 Для привязки введите код из личного кабинета:\n"
                    "Формат: привязать 123456"
                )
        else:
            return (
                "👋 Привет! Ваш аккаунт не привязан.\n"
                "Получите код в личном кабинете и отправьте: привязать КОД"
            )

    # Обработка команд
    if message_text == "помощь":
        return (
            "📋 *Команды:*\n"
            "дети - список ваших детей\n"
            "сегодня - сегодняшние тренировки\n"
            "неделя - тренировки на неделю\n"
            "уведомления вкл/выкл - настройка уведомлений"
        )
    elif message_text == "дети":
        return get_children_info(parent, db)
    elif message_text == "сегодня":
        return get_today_trainings(parent, db)
    elif message_text == "неделя":
        return get_week_trainings(parent, db)
    elif message_text == "уведомления вкл":
        parent.notify_reminders = True
        db.commit()
        return "✅ Уведомления включены!"
    elif message_text == "уведомления выкл":
        parent.notify_reminders = False
        db.commit()
        return "🔕 Уведомления выключены!"
    else:
        return "Неизвестная команда. Напишите 'помощь' для списка команд."


def link_parent_by_code(user_vk_id: int, code: str, db: Session) -> str:
    """Привязка родителя по коду"""
    parent = db.query(ParentDB).filter(
        ParentDB.vk_link_code == code,
        ParentDB.vk_code_expires_at > datetime.now(),
        ParentDB.is_active == True
    ).first()

    if not parent:
        return "❌ Неверный или просроченный код"

    parent.vk_id = user_vk_id
    parent.is_vk_linked = True
    parent.vk_link_code = None
    parent.vk_code_expires_at = None
    db.commit()

    return f"✅ Аккаунт привязан! Теперь вы будете получать уведомления о тренировках {parent.name}"


def get_children_info(parent: ParentDB, db: Session) -> str:
    """Информация о детях"""
    children = db.query(ChildDB).filter(
        ChildDB.parent_id == parent.id,
        ChildDB.is_active == True
    ).all()

    if not children:
        return "У вас нет зарегистрированных детей"

    result = "👶 *Ваши дети:*\n\n"
    for child in children:
        from database import EnrollmentDB, EnrollmentStatus
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        group_name = enrollment.group.name if enrollment else "Не назначена"
        result += f"• {child.name} - {group_name}\n"

    return result


def get_today_trainings(parent: ParentDB, db: Session) -> str:
    """Сегодняшние тренировки детей"""
    today = datetime.now().date()

    children = db.query(ChildDB).filter(
        ChildDB.parent_id == parent.id,
        ChildDB.is_active == True
    ).all()

    result = f"📅 *Тренировки на {today.strftime('%d.%m.%Y')}:*\n\n"
    has_trainings = False

    for child in children:
        from database import EnrollmentDB, EnrollmentStatus, TrainingDB
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        if enrollment and enrollment.group:
            training = db.query(TrainingDB).filter(
                TrainingDB.group_id == enrollment.group_id,
                TrainingDB.date == today,
                TrainingDB.status == "scheduled"
            ).first()

            if training:
                has_trainings = True
                result += f"{child.name}: {training.start_time.strftime('%H:%M')}-{training.end_time.strftime('%H:%M')}\n"

    if not has_trainings:
        return "Сегодня тренировок нет"

    return result


def get_week_trainings(parent: ParentDB, db: Session) -> str:
    """Тренировки на неделю"""
    today = datetime.now().date()
    week_end = today + timedelta(days=7)

    children = db.query(ChildDB).filter(
        ChildDB.parent_id == parent.id,
        ChildDB.is_active == True
    ).all()

    result = "📅 *Тренировки на неделю:*\n\n"
    days_names = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]

    for child in children:
        from database import EnrollmentDB, EnrollmentStatus, TrainingDB
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        if enrollment and enrollment.group:
            trainings = db.query(TrainingDB).filter(
                TrainingDB.group_id == enrollment.group_id,
                TrainingDB.date >= today,
                TrainingDB.date <= week_end,
                TrainingDB.status == "scheduled"
            ).order_by(TrainingDB.date).all()

            if trainings:
                result += f"\n*{child.name}*\n"
                for t in trainings:
                    day_name = days_names[t.date.weekday()]
                    result += f"  {day_name} {t.date.strftime('%d.%m')}: {t.start_time.strftime('%H:%M')}\n"

    return result


def start_vk_worker():
    """Запуск фонового процесса (упрощённо)"""
    if not VK_ENABLED:
        print("[VK] Бот отключён. Для включения установите VK_ENABLED = True и настройте токен")
        return

    if not VK_USER_TOKEN or VK_USER_TOKEN == "YOUR_VK_TOKEN_HERE":
        print("[VK] Токен не настроен! Получите токен на https://vkhost.github.io/")
        return

    print("[VK] Бот настроен и готов к работе!")