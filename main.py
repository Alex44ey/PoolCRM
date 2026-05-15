# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from database import engine, Base
from api_routes import router
import os
from vk_bot import start_vk_worker


# ========== LIFESPAN (ОБНОВЛЕННАЯ ВЕРСИЯ С VK БОТОМ) ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск приложения...")
    print("📦 Создаю таблицы в базе данных...")
    Base.metadata.create_all(bind=engine)

    # Запускаем VK бота в фоновом режиме
    print("🤖 Запускаю VK бота...")
    start_vk_worker()
    print("✅ VK бот запущен!")

    print("✅ Приложение готово к работе!")
    yield
    print("🛑 Завершаю работу приложения...")


# ========== СОЗДАНИЕ ПРИЛОЖЕНИЯ ==========
app = FastAPI(
    title="Pool CRM",
    description="CRM система для управления бассейном",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# ========== СОЗДАНИЕ STATIC HTML ==========

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index():
    """Главная страница"""
    return FileResponse("static/index.html")


# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == "__main__":
    import uvicorn

    print("🐬 Запуск Pool CRM сервера...")
    print("📍 Адрес: http://127.0.0.1:8000")
    print("📖 Документация: http://127.0.0.1:8000/docs")
    print("🔑 Тестовые учётные записи:")
    print("   👑 Админ: admin@pool.ru / admin123")
    print("   👨‍👩‍👧 Родители: maria@example.com / parent123")
    print("   🏊‍♂️ Тренеры: ivan.coach@pool.ru / coach123")

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )