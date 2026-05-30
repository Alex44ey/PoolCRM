# vk_bot.py
"""
VK бот для уведомлений о посещаемости
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any

import requests
from sqlalchemy.orm import Session

from database import (
    ParentDB, ChildDB, TrainingDB,
    EnrollmentDB, EnrollmentStatus, GroupDB
)

# ========== НАСТРОЙКИ ==========
VK_API_VERSION = "5.131"
LONG_POLL_WAIT = 25


VK_USER_TOKEN = "vk1.a.2L7Da-FDfqJis-ZAv53elax3GGaIx8s2l9ZQXAcuZg1cniV3AGUlPA02YFX08sBVU2EJKa6FFcq1PTRn3k1TOvKzhkQHDduXnME4Ff2Ilv53xrpdLFbiQfU3ruLQ9-DX6yup9qFlaSCeinFwmQEARlplNvhtpml_UwlLNs8Ng5t05cusjfR7o20iWTFtMwdqqQxaNgbYk7qw9S_-tS4SZg"
VK_ENABLED = True

# Глобальные переменные
_running = False
_listener_thread = None
_db_factory = None


def send_vk_message(user_vk_id: int, message: str) -> bool:
    """
    Отправка сообщения пользователю VK через messages.send

    Args:
        user_vk_id: ID пользователя VK
        message: Текст сообщения

    Returns:
        bool: Успешность отправки
    """
    if not VK_ENABLED:
        print(f"[VK] Бот отключён")
        return False

    if not VK_USER_TOKEN:
        print("[VK] Токен не настроен!")
        return False

    if not user_vk_id:
        print("[VK] Не указан user_vk_id")
        return False

    try:
        url = "https://api.vk.com/method/messages.send"

        # Для групповых сообщений нужно указывать peer_id
        params = {
            "user_id": user_vk_id,
            "random_id": int(time.time() * 1000),
            "message": message,
            "access_token": VK_USER_TOKEN,
            "v": VK_API_VERSION
        }

        response = requests.post(url, params=params, timeout=10)
        data = response.json()

        if "error" in data:
            error = data["error"]
            error_msg = error.get("error_msg", "Unknown error")
            error_code = error.get("error_code", 0)

            # 901: Can't send messages for this user (пользователь не написал боту первым)
            if error_code == 901:
                print(f"[VK] Пользователь {user_vk_id} не начал диалог с ботом")
            else:
                print(f"[VK] Ошибка {error_code}: {error_msg}")
            return False

        print(f"[VK] Сообщение отправлено пользователю {user_vk_id}")
        return True

    except requests.exceptions.Timeout:
        print(f"[VK] Таймаут при отправке сообщения")
        return False
    except Exception as e:
        print(f"[VK] Ошибка отправки: {e}")
        return False


def send_vk_peer_message(peer_id: int, message: str) -> bool:
    """
    Отправка сообщения в диалог (для групповых чатов)

    Args:
        peer_id: ID диалога (для личных - user_id, для бесед - 2000000000 + id)
        message: Текст сообщения
    """
    if not VK_ENABLED or not VK_USER_TOKEN:
        return False

    try:
        url = "https://api.vk.com/method/messages.send"
        params = {
            "peer_id": peer_id,
            "random_id": int(time.time() * 1000),
            "message": message,
            "access_token": VK_USER_TOKEN,
            "v": VK_API_VERSION
        }

        response = requests.post(url, params=params, timeout=10)
        data = response.json()

        if "error" in data:
            print(f"[VK] Ошибка отправки в peer {peer_id}: {data['error']}")
            return False

        return True
    except Exception as e:
        print(f"[VK] Ошибка: {e}")
        return False


def send_attendance_notification_vk(
        child_id: int,
        training_id: int,
        status: str,
        db: Session
) -> bool:
    """
    Отправка уведомления родителю о посещаемости

    Args:
        child_id: ID ребёнка
        training_id: ID тренировки
        status: Статус посещаемости (present, absent_sick, absent_family, absent_no_reason)
        db: Сессия БД

    Returns:
        bool: Успешность отправки
    """
    if not VK_ENABLED:
        return False

    try:
        # Получаем информацию о ребёнке
        child = db.query(ChildDB).filter(ChildDB.id == child_id).first()
        if not child or not child.parent:
            return False

        parent = child.parent

        # Проверяем, привязан ли VK
        if not parent.is_vk_linked or not parent.vk_id:
            return False

        # Проверяем настройки уведомлений
        if status == "absent_sick" and not parent.notify_absences:
            return False
        if status == "present" and not parent.notify_reminders:
            return False

        # Получаем информацию о тренировке
        training = db.query(TrainingDB).filter(TrainingDB.id == training_id).first()
        if not training:
            return False

        group_name = training.group.name if training.group else "Неизвестная группа"
        date_str = training.date.strftime('%d.%m.%Y')

        # Формируем сообщение в зависимости от статуса
        status_messages = {
            "present": (
                f"✅ *{child.name} присутствовал на тренировке!*\n\n"
                f"📅 Дата: {date_str}\n"
                f"👥 Группа: {group_name}\n"
                f"⏰ Время: {training.start_time.strftime('%H:%M')}\n\n"
                f"🏊‍♂️ Хорошая работа!"
            ),
            "absent_sick": (
                f"❌ *{child.name} отсутствовал на тренировке по болезни*\n\n"
                f"📅 Дата: {date_str}\n"
                f"👥 Группа: {group_name}\n\n"
                f"🌡️ Желаем скорейшего выздоровления!"
            ),
            "absent_family": (
                f"❌ *{child.name} отсутствовал на тренировке*\n\n"
                f"📅 Дата: {date_str}\n"
                f"👥 Группа: {group_name}\n\n"
                f"📌 Причина: семейные обстоятельства"
            ),
            "absent_no_reason": (
                f"⚠️ *{child.name} отсутствовал на тренировке БЕЗ УВАЖИТЕЛЬНОЙ ПРИЧИНЫ!*\n\n"
                f"📅 Дата: {date_str}\n"
                f"👥 Группа: {group_name}\n\n"
                f"Пожалуйста, сообщите тренеру о причинах пропуска."
            )
        }

        message = status_messages.get(status)
        if not message:
            return False

        return send_vk_message(parent.vk_id, message)

    except Exception as e:
        print(f"[VK] Ошибка отправки уведомления: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_long_poll_server() -> Optional[Dict[str, Any]]:
    """Получение сервера для Long Poll"""
    try:
        url = "https://api.vk.com/method/messages.getLongPollServer"
        params = {
            "access_token": VK_USER_TOKEN,
            "v": VK_API_VERSION,
            "lp_version": 3,
            "need_pts": 0
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "error" in data:
            error = data["error"]
            print(f"[VK] Ошибка получения Long Poll сервера: {error.get('error_msg', 'Unknown')}")
            return None

        if "response" not in data:
            print(f"[VK] Неожиданный ответ: {data}")
            return None

        server_data = data["response"]

        # ИСПРАВЛЕНО: правильно добавляем https://
        server = server_data.get("server", "")
        # Убираем возможный слеш в начале
        server = server.lstrip('/')
        # Добавляем https:// если нет схемы
        if server and not server.startswith(("http://", "https://")):
            server = "https://" + server

        return {
            "server": server,
            "key": server_data.get("key"),
            "ts": server_data.get("ts")
        }

    except Exception as e:
        print(f"[VK] Ошибка: {e}")
        return None


def process_long_poll_updates(updates: list, db_factory: Callable):
    """
    Обработка обновлений от Long Poll сервера

    Формат обновлений VK Long Poll версии 3:
    update = [code, ...]
    code 4 - новое сообщение
    """
    for update in updates:
        if not isinstance(update, list) or len(update) < 1:
            continue

        code = update[0]

        # Новое сообщение (code 4)
        if code == 4:
            # Формат: [4, message_id, flags, peer_id, timestamp, text, additional_info...]
            if len(update) < 6:
                continue

            message_id = update[1]
            flags = update[2]
            peer_id = update[3]
            timestamp = update[4]
            text = update[5]

            # Проверяем, что сообщение не от самого бота (флаг out)
            if flags & 2:
                continue

            # Получаем user_id (для личных сообщений peer_id = user_id)
            user_id = peer_id if peer_id < 2000000000 else None

            if user_id and text:
                print(f"[VK] Получено сообщение от {user_id}: {text[:50]}...")

                # Обрабатываем в отдельном потоке, чтобы не блокировать Long Poll
                threading.Thread(
                    target=handle_incoming_message,
                    args=(user_id, text, db_factory),
                    daemon=True
                ).start()


def handle_incoming_message(user_id: int, text: str, db_factory: Callable):
    """
    Обработка входящего сообщения
    """
    db = db_factory()
    try:
        response = process_vk_message(user_id, text.strip(), db)
        if response:
            send_vk_message(user_id, response)
    except Exception as e:
        print(f"[VK] Ошибка обработки сообщения: {e}")
    finally:
        db.close()


def process_vk_message(user_vk_id: int, message_text: str, db: Session) -> str:
    """
    Обработка входящего сообщения от пользователя

    Args:
        user_vk_id: VK ID пользователя
        message_text: Текст сообщения
        db: Сессия БД

    Returns:
        str: Текст ответа
    """
    message_text = message_text.lower().strip()

    # Поиск родителя по VK ID
    parent = db.query(ParentDB).filter(
        ParentDB.vk_id == user_vk_id,
        ParentDB.is_active == True
    ).first()

    # Если родитель не найден - пытаемся привязать
    if not parent:
        if message_text.startswith("привязать"):
            parts = message_text.split()
            if len(parts) >= 2:
                code = parts[1]
                return link_parent_by_code(user_vk_id, code, db)
            else:
                return (
                    "🔗 *Для привязки аккаунта*\n\n"
                    "Получите код в личном кабинете и отправьте:\n"
                    "`привязать КОД`\n\n"
                    "Пример: привязать 123456"
                )
        else:
            return (
                "👋 *Привет!*\n\n"
                "Ваш аккаунт не привязан к системе.\n\n"
                "🔗 Для привязки:\n"
                "1. Войдите в личный кабинет\n"
                "2. Получите код в разделе 'Профиль'\n"
                "3. Отправьте команду:\n"
                "`привязать КОД`"
            )

    # Обработка команд для привязанного родителя
    if message_text in ["помощь", "help", "?"]:
        return (
            "📋 *Команды бота*\n\n"
            "🔹 `дети` - список ваших детей\n"
            "🔹 `сегодня` - сегодняшние тренировки\n"
            "🔹 `завтра` - завтрашние тренировки\n"
            "🔹 `неделя` - тренировки на неделю\n"
            "🔹 `уведомления вкл` - включить уведомления\n"
            "🔹 `уведомления выкл` - выключить уведомления\n"
            "🔹 `помощь` - показать это сообщение\n\n"
            "💡 *Статус уведомлений:*\n"
            f"{'✅' if parent.notify_reminders else '❌'} Оповещения {'включены' if parent.notify_reminders else 'выключены'}"
        )

    elif message_text == "дети":
        return get_children_info(parent, db)

    elif message_text == "сегодня":
        return get_trainings_for_date(parent, db, datetime.now().date())

    elif message_text == "завтра":
        tomorrow = datetime.now().date() + timedelta(days=1)
        return get_trainings_for_date(parent, db, tomorrow)

    elif message_text == "неделя":
        return get_week_trainings(parent, db)

    elif message_text == "уведомления вкл":
        parent.notify_reminders = True
        db.commit()
        return "✅ Уведомления включены! Вы будете получать оповещения о тренировках."

    elif message_text == "уведомления выкл":
        parent.notify_reminders = False
        db.commit()
        return "🔕 Уведомления выключены. Вы не будете получать оповещения."

    else:
        return (
            "❓ *Неизвестная команда*\n\n"
            "Напишите `помощь` для списка доступных команд."
        )


def link_parent_by_code(user_vk_id: int, code: str, db: Session) -> str:
    """
    Привязка родителя по коду
    """
    parent = db.query(ParentDB).filter(
        ParentDB.vk_link_code == code,
        ParentDB.vk_code_expires_at > datetime.now(),
        ParentDB.is_active == True
    ).first()

    if not parent:
        return (
            "❌ *Неверный или просроченный код*\n\n"
            "Получите новый код в личном кабинете и попробуйте снова."
        )

    # Проверяем, не привязан ли уже этот VK к другому родителю
    existing = db.query(ParentDB).filter(
        ParentDB.vk_id == user_vk_id,
        ParentDB.id != parent.id
    ).first()

    if existing:
        return (
            "⚠️ *Этот VK аккаунт уже привязан*\n\n"
            "Если вы хотите привязать его к другому родителю, "
            "сначала отвяжите его в личном кабинете."
        )

    parent.vk_id = user_vk_id
    parent.is_vk_linked = True
    parent.vk_link_code = None
    parent.vk_code_expires_at = None
    db.commit()

    return (
        f"✅ *Аккаунт успешно привязан!*\n\n"
        f"👋 Здравствуйте, {parent.name}!\n\n"
        f"Теперь вы будете получать уведомления о тренировках ваших детей.\n\n"
        f"Напишите `помощь` чтобы узнать доступные команды."
    )


def get_children_info(parent: ParentDB, db: Session) -> str:
    """
    Информация о детях родителя
    """
    children = db.query(ChildDB).filter(
        ChildDB.parent_id == parent.id,
        ChildDB.is_active == True
    ).all()

    if not children:
        return "👶 У вас нет зарегистрированных детей"

    result = "👶 *Ваши дети:*\n\n"

    for child in children:
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        group_name = enrollment.group.name if enrollment and enrollment.group else "Не назначена"
        age = (datetime.now().date() - child.birthdate).days // 365 if child.birthdate else "?"

        result += f"• **{child.name}**\n"
        result += f"  🏊 Группа: {group_name}\n"
        result += f"  🎂 Возраст: {age} лет\n\n"

    return result


def get_trainings_for_date(parent: ParentDB, db: Session, target_date) -> str:
    """
    Получение тренировок на указанную дату
    """
    children = db.query(ChildDB).filter(
        ChildDB.parent_id == parent.id,
        ChildDB.is_active == True
    ).all()

    if not children:
        return "У вас нет зарегистрированных детей"

    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    date_str = target_date.strftime('%d.%m.%Y')
    weekday = weekday_names[target_date.weekday()]

    result = f"📅 *Тренировки на {date_str} ({weekday})*\n\n"
    has_trainings = False

    for child in children:
        enrollment = db.query(EnrollmentDB).filter(
            EnrollmentDB.child_id == child.id,
            EnrollmentDB.status == EnrollmentStatus.ACTIVE
        ).first()

        if enrollment and enrollment.group:
            training = db.query(TrainingDB).filter(
                TrainingDB.group_id == enrollment.group_id,
                TrainingDB.date == target_date,
                TrainingDB.status == "scheduled"
            ).first()

            if training:
                has_trainings = True
                start_time = training.start_time.strftime('%H:%M')
                end_time = training.end_time.strftime('%H:%M')
                result += f"🏊‍♂️ **{child.name}**\n"
                result += f"   {start_time} - {end_time}\n"
                result += f"   📍 {enrollment.group.name}\n\n"

    if not has_trainings:
        if target_date == datetime.now().date():
            return "📭 Сегодня тренировок нет"
        elif target_date == (datetime.now().date() + timedelta(days=1)):
            return "📭 На завтра тренировок нет"
        else:
            return f"📭 На {date_str} тренировок нет"

    return result


def get_week_trainings(parent: ParentDB, db: Session) -> str:
    """
    Тренировки на текущую неделю
    """
    today = datetime.now().date()
    week_end = today + timedelta(days=7)

    children = db.query(ChildDB).filter(
        ChildDB.parent_id == parent.id,
        ChildDB.is_active == True
    ).all()

    if not children:
        return "У вас нет зарегистрированных детей"

    result = "📅 *Тренировки на неделю*\n"
    days_names = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    has_any = False

    for child in children:
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
                has_any = True
                result += f"\n👶 **{child.name}**\n"
                for t in trainings:
                    day_name = days_names[t.date.weekday()]
                    result += f"   {day_name} {t.date.strftime('%d.%m')}: {t.start_time.strftime('%H:%M')}\n"

    if not has_any:
        return "📭 На этой неделе тренировок нет"

    return result


def listen_for_messages(db_factory: Callable):
    """Основной цикл прослушивания сообщений VK"""
    global _running

    print("[VK] Запуск Long Poll listener...")

    if not VK_USER_TOKEN:
        print("[VK] Токен не настроен! Бот не будет работать.")
        return

    while _running:
        try:
            server_data = get_long_poll_server()
            if not server_data:
                print("[VK] Не удалось получить сервер, повтор через 30 секунд...")
                time.sleep(30)
                continue

            server = server_data.get("server")
            key = server_data.get("key")
            ts = server_data.get("ts")

            if not server or not key or not ts:
                print(f"[VK] Неполные данные сервера: {server_data}")
                time.sleep(30)
                continue

            print(f"[VK] Подключение к Long Poll серверу: {server}")

            while _running:
                try:
                    # ИСПРАВЛЕНО: убеждаемся что server имеет правильный формат
                    # Убираем возможные лишние слеши
                    base_server = server.rstrip('/')
                    url = f"{base_server}?act=a_check&key={key}&ts={ts}&wait={LONG_POLL_WAIT}&mode=2&version=3"

                    print(f"[VK DEBUG] Запрос к: {url[:100]}...")  # Отладка

                    response = requests.get(url, timeout=LONG_POLL_WAIT + 5)
                    data = response.json()

                    if "failed" in data:
                        failed_code = data["failed"]
                        print(f"[VK] Long Poll failed: code {failed_code}")

                        if failed_code == 1:
                            ts = data.get("ts", ts)
                        break

                    if "ts" in data:
                        ts = data["ts"]

                    if "updates" in data and isinstance(data["updates"], list):
                        process_long_poll_updates(data["updates"], db_factory)

                except requests.exceptions.Timeout:
                    continue
                except Exception as e:
                    print(f"[VK] Ошибка в Long Poll цикле: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(5)
                    break

        except Exception as e:
            print(f"[VK] Критическая ошибка: {e}")
            time.sleep(30)


def start_vk_worker(db_factory: Callable = None):
    """
    Запуск VK бота в фоновом потоке

    Args:
        db_factory: Функция для создания сессии БД (например, SessionLocal)
    """
    global _running, _listener_thread, _db_factory

    if not VK_ENABLED:
        print("[VK] Бот отключён (VK_ENABLED=False)")
        print("[VK] Для включения установите VK_ENABLED=True в .env")
        return

    if not VK_USER_TOKEN:
        print("[VK] Токен не настроен!")
        print("[VK] Добавьте VK_USER_TOKEN в файл .env")
        print("[VK] Получить токен можно здесь: https://vkhost.github.io/")
        print("[VK] Выберите разрешения: messages, offline")
        return

    if _running:
        print("[VK] Бот уже запущен")
        return

    if db_factory is None:
        from database import SessionLocal
        db_factory = SessionLocal

    _db_factory = db_factory
    _running = True

    # Запускаем слушатель в отдельном потоке
    _listener_thread = threading.Thread(
        target=listen_for_messages,
        args=(db_factory,),
        daemon=True
    )
    _listener_thread.start()

    print("[VK] ✅ Бот успешно запущен и слушает сообщения!")
    print(f"[VK] Токен: {VK_USER_TOKEN[:20]}...")

    # Отправляем тестовое сообщение себе (опционально)
    # send_vk_message(YOUR_USER_ID, "🤖 Бот запущен и готов к работе!")


def stop_vk_worker():
    """
    Остановка VK бота
    """
    global _running

    print("[VK] Остановка бота...")
    _running = False

    if _listener_thread:
        _listener_thread.join(timeout=5)

    print("[VK] Бот остановлен")


def get_bot_status() -> dict:
    """
    Получение статуса бота
    """
    return {
        "enabled": VK_ENABLED,
        "running": _running,
        "token_configured": bool(VK_USER_TOKEN),
        "token_preview": VK_USER_TOKEN[:20] + "..." if VK_USER_TOKEN else None
    }


# Для тестирования
if __name__ == "__main__":
    print("=" * 50)
    print("VK Бот - Тестовый запуск")
    print("=" * 50)

    from database import SessionLocal

    start_vk_worker(SessionLocal)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        stop_vk_worker()
        print("Тест завершён")