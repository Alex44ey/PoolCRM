# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import engine, Base


# ========== LIFESPAN (ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ) ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Выполняется при запуске и остановке приложения
    """
    print("🚀 Запуск приложения...")

    # Создаём таблицы в базе данных (если их нет)
    print("📦 Создаю таблицы в базе данных...")
    Base.metadata.create_all(bind=engine)

    print("✅ Приложение готово к работе!")

    yield  # Здесь приложение работает

    # Код при остановке
    print("🛑 Завершаю работу приложения...")

# ========== СОЗДАНИЕ ПРИЛОЖЕНИЯ ==========
app = FastAPI(
    title="Pool CRM",
    description="CRM система для управления бассейном",
    version="1.0.0",
    lifespan=lifespan
)

# ========== ЭНДПОИНТЫ ==========
@app.get("/")
async def root():
    """Главный эндпоинт для проверки работы API"""
    return {
        "message": "Pool CRM API работает",
        "status": "online",
        "version": "1.0.0"
    }

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == "__main__":
    import uvicorn

    print("🐬 Запуск Pool CRM сервера...")
    print("📍 Адрес: http://127.0.0.1:8000")
    print("📖 Документация: http://127.0.0.1:8000/docs")

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True  # Автоматическая перезагрузка при изменении кода
    )