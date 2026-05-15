# main.py
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from database import engine, Base
from api_routes import router
import os


# ========== LIFESPAN ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск приложения...")
    print("📦 Создаю таблицы в базе данных...")
    Base.metadata.create_all(bind=engine)
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
os.makedirs("static", exist_ok=True)

HTML_CONTENT = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pool CRM - Управление бассейном</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: rgba(255, 255, 255, 0.95); border-radius: 15px; padding: 20px 30px; margin-bottom: 30px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
        .logo h1 { color: #667eea; font-size: 28px; }
        .logo p { color: #666; font-size: 14px; }
        .user-info { display: flex; align-items: center; gap: 15px; }
        .user-name { font-weight: 600; color: #333; }
        .logout-btn { background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 8px; cursor: pointer; transition: all 0.3s; }
        .logout-btn:hover { background: #c82333; transform: translateY(-2px); }
        .nav-menu { background: white; border-radius: 15px; padding: 15px 20px; margin-bottom: 30px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); display: flex; gap: 10px; flex-wrap: wrap; }
        .nav-btn { background: #f0f0f0; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; transition: all 0.3s; font-size: 14px; font-weight: 500; }
        .nav-btn:hover { background: #667eea; color: white; transform: translateY(-2px); }
        .nav-btn.active { background: #667eea; color: white; }
        .content { background: white; border-radius: 15px; padding: 30px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); min-height: 500px; }
        .page { display: none; }
        .page.active-page { display: block; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-number { font-size: 36px; font-weight: bold; margin-bottom: 10px; }
        .stat-label { font-size: 14px; opacity: 0.9; }
        .data-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .data-table th, .data-table td { padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }
        .data-table th { background: #f8f9fa; font-weight: 600; color: #667eea; }
        .data-table tr:hover { background: #f8f9fa; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; transition: border-color 0.3s; }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { outline: none; border-color: #667eea; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.3s; }
        .btn-primary { background: #667eea; color: white; }
        .btn-primary:hover { background: #5a67d8; transform: translateY(-2px); }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
        .status-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }
        .status-active { background: #d4edda; color: #155724; }
        .status-frozen { background: #fff3cd; color: #856404; }
        .status-completed { background: #d1ecf1; color: #0c5460; }
        .status-present { background: #d4edda; color: #155724; }
        .status-absent { background: #f8d7da; color: #721c24; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }
        .modal-content { background: white; border-radius: 15px; padding: 30px; max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .close { font-size: 28px; cursor: pointer; color: #999; }
        .close:hover { color: #333; }
        .alert { padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; display: none; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .login-container { max-width: 400px; margin: 100px auto; background: white; border-radius: 15px; padding: 40px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
        .login-title { text-align: center; color: #667eea; margin-bottom: 30px; }
        @media (max-width: 768px) { .header { flex-direction: column; text-align: center; gap: 15px; } .stats-grid { grid-template-columns: 1fr; } .data-table { font-size: 12px; } .data-table th, .data-table td { padding: 8px; } }
    </style>
</head>
<body>
    <div id="loginPage" class="login-container">
        <h2 class="login-title">🐬 Pool CRM</h2>
        <form id="loginForm">
            <div class="form-group"><label>Email</label><input type="email" id="loginEmail" required></div>
            <div class="form-group"><label>Пароль</label><input type="password" id="loginPassword" required></div>
            <button type="submit" class="btn btn-primary" style="width: 100%;">Войти</button>
        </form>
        <div id="loginError" class="alert alert-error" style="margin-top: 20px;"></div>
    </div>
    <div id="mainApp" style="display: none;">
        <div class="container">
            <div class="header">
                <div class="logo"><h1>🐬 Pool CRM</h1><p>Система управления бассейном</p></div>
                <div class="user-info"><span class="user-name" id="userName"></span><button class="logout-btn" onclick="logout()">Выйти</button></div>
            </div>
            <div class="nav-menu">
                <button class="nav-btn active" onclick="showPage('dashboard')">📊 Дашборд</button>
                <button class="nav-btn" onclick="showPage('children')">👶 Дети</button>
                <button class="nav-btn" onclick="showPage('groups')">👥 Группы</button>
                <button class="nav-btn" onclick="showPage('trainings')">🏊 Тренировки</button>
                <button class="nav-btn" onclick="showPage('attendance')">📊 Посещаемость</button>
                <button class="nav-btn" onclick="showPage('applications')">📋 Заявки</button>
                <button class="nav-btn" onclick="showPage('coaches')">🏊‍♂️ Тренеры</button>
                <button class="nav-btn" onclick="showPage('transfers')">🔄 Переводы</button>
            </div>
            <div class="content">
                <div id="dashboardPage" class="page active-page">
                    <h2>Дашборд</h2>
                    <div class="stats-grid" id="statsGrid"></div>
                </div>

                <div id="childrenPage" class="page">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2>Управление детьми</h2>
                        <button class="btn btn-primary" onclick="openChildModal()">+ Добавить ребёнка</button>
                    </div>
                    <table class="data-table" id="childrenTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Имя</th>
                                <th>Дата рождения</th>
                                <th>Класс</th>
                                <th>Группа</th>
                                <th>Статус</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="childrenTableBody"></tbody>
                    </table>
                </div>

                <div id="groupsPage" class="page">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2>Группы</h2>
                        <button class="btn btn-primary" onclick="openGroupModal()">+ Создать группу</button>
                    </div>
                    <table class="data-table" id="groupsTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Название</th>
                                <th>Уровень</th>
                                <th>Тренер</th>
                                <th>Макс. мест</th>
                                <th>Заполнено</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="groupsTableBody"></tbody>
                    </table>
                </div>

                <div id="trainingsPage" class="page">
                    <h2>Тренировки</h2>
                    <div class="form-group">
                        <label>Фильтр по группе</label>
                        <select id="trainingGroupFilter" onchange="loadTrainings()">
                            <option value="">Все группы</option>
                        </select>
                    </div>
                    <table class="data-table" id="trainingsTable">
                        <thead>
                            <tr>
                                <th>Дата</th>
                                <th>Группа</th>
                                <th>Время</th>
                                <th>Статус</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="trainingsTableBody"></tbody>
                    </table>
                </div>

                <div id="attendancePage" class="page">
                    <h2>Посещаемость</h2>
                    <div class="form-group">
                        <label>Выберите тренировку</label>
                        <select id="attendanceTraining" onchange="loadAttendance()">
                            <option value="">Выберите тренировку</option>
                        </select>
                    </div>
                    <div id="attendanceForm"></div>
                </div>

                <div id="applicationsPage" class="page">
                    <h2>Заявки на зачисление</h2>
                    <table class="data-table" id="applicationsTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Ребёнок</th>
                                <th>Группа</th>
                                <th>Статус</th>
                                <th>Дата</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="applicationsTableBody"></tbody>
                    </table>
                </div>

                <div id="coachesPage" class="page">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2>Тренеры</h2>
                        <button class="btn btn-primary" onclick="openCoachModal()">+ Добавить тренера</button>
                    </div>
                    <table class="data-table" id="coachesTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Имя</th>
                                <th>Email</th>
                                <th>Телефон</th>
                                <th>Группы</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="coachesTableBody"></tbody>
                    </table>
                </div>

                <div id="transfersPage" class="page">
                    <h2>Запросы на перевод</h2>
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-primary" onclick="openTransferRequestModal()">+ Создать запрос</button>
                    </div>
                    <table class="data-table" id="transfersTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Ребёнок</th>
                                <th>Из группы</th>
                                <th>В группу</th>
                                <th>Статус</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="transfersTableBody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Modals -->
    <div id="childModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="childModalTitle">Добавить ребёнка</h3>
                <span class="close" onclick="closeChildModal()">&times;</span>
            </div>
            <form id="childForm">
                <input type="hidden" id="childId">
                <div class="form-group"><label>Имя ребёнка</label><input type="text" id="childName" required></div>
                <div class="form-group"><label>Дата рождения</label><input type="date" id="childBirthdate" required></div>
                <div class="form-group"><label>Класс</label><input type="number" id="childClass"></div>
                <div class="form-group"><label>Год обучения</label><input type="number" id="childStudyYear"></div>
                <div class="form-group"><label>Медицинская справка</label><textarea id="childMedicalNote"></textarea></div>
                <button type="submit" class="btn btn-primary">Сохранить</button>
            </form>
        </div>
    </div>

    <div id="groupModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="groupModalTitle">Создать группу</h3>
                <span class="close" onclick="closeGroupModal()">&times;</span>
            </div>
            <form id="groupForm">
                <input type="hidden" id="groupId">
                <div class="form-group"><label>Название группы</label><input type="text" id="groupName" required></div>
                <div class="form-group"><label>Уровень (0-5)</label><input type="number" id="groupLevel" min="0" max="5" required></div>
                <div class="form-group"><label>Тренер</label><select id="groupCoachId" required></select></div>
                <div class="form-group"><label>Максимальное количество</label><input type="number" id="groupMaxCapacity" required></div>
                <button type="submit" class="btn btn-primary">Сохранить</button>
            </form>
        </div>
    </div>

    <div id="coachModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="coachModalTitle">Добавить тренера</h3>
                <span class="close" onclick="closeCoachModal()">&times;</span>
            </div>
            <form id="coachForm">
                <input type="hidden" id="coachId">
                <div class="form-group"><label>Имя тренера</label><input type="text" id="coachName" required></div>
                <div class="form-group"><label>Email</label><input type="email" id="coachEmail" required></div>
                <div class="form-group"><label>Телефон</label><input type="text" id="coachPhone"></div>
                <div class="form-group"><label>Пароль</label><input type="password" id="coachPassword"></div>
                <button type="submit" class="btn btn-primary">Сохранить</button>
            </form>
        </div>
    </div>

    <div id="transferModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Запрос на перевод</h3>
                <span class="close" onclick="closeTransferModal()">&times;</span>
            </div>
            <form id="transferForm">
                <div class="form-group"><label>Ребёнок</label><select id="transferChildId" required></select></div>
                <div class="form-group"><label>Текущая группа</label><select id="transferFromGroupId" required></select></div>
                <div class="form-group"><label>Предлагаемая группа</label><select id="transferSuggestedGroupId" required></select></div>
                <div class="form-group"><label>Комментарий</label><textarea id="transferComment"></textarea></div>
                <button type="submit" class="btn btn-primary">Отправить запрос</button>
            </form>
        </div>
    </div>

    <div id="alertMessage" class="alert"></div>

    <script>
        const API_BASE = '/api';
        let currentUser = null;

        document.addEventListener('DOMContentLoaded', () => { 
            checkAuth(); 
            document.getElementById('loginForm').addEventListener('submit', handleLogin); 
            document.getElementById('childForm').addEventListener('submit', saveChild); 
            document.getElementById('groupForm').addEventListener('submit', saveGroup); 
            document.getElementById('coachForm').addEventListener('submit', saveCoach); 
            document.getElementById('transferForm').addEventListener('submit', saveTransferRequest); 
        });

        function checkAuth() { 
            const savedUser = localStorage.getItem('currentUser'); 
            if (savedUser) { 
                currentUser = JSON.parse(savedUser); 
                showMainApp(); 
                loadDashboard(); 
                loadAllData(); 
            } 
        }

        async function handleLogin(e) { 
            e.preventDefault(); 
            const email = document.getElementById('loginEmail').value; 
            const password = document.getElementById('loginPassword').value; 
            try { 
                const response = await fetch(`${API_BASE}/auth/login`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify({ email, password }) 
                }); 
                if (response.ok) { 
                    const user = await response.json(); 
                    currentUser = user; 
                    localStorage.setItem('currentUser', JSON.stringify(user)); 
                    showMainApp(); 
                    loadDashboard(); 
                    loadAllData(); 
                } else { 
                    showLoginError('Неверный email или пароль'); 
                } 
            } catch (error) { 
                showLoginError('Ошибка подключения к серверу'); 
            } 
        }

        function showLoginError(message) { 
            const errorDiv = document.getElementById('loginError'); 
            errorDiv.textContent = message; 
            errorDiv.style.display = 'block'; 
            setTimeout(() => { errorDiv.style.display = 'none'; }, 3000); 
        }

        function showMainApp() { 
            document.getElementById('loginPage').style.display = 'none'; 
            document.getElementById('mainApp').style.display = 'block'; 
            document.getElementById('userName').textContent = currentUser?.name || 'Пользователь'; 
        }

        function logout() { 
            localStorage.removeItem('currentUser'); 
            currentUser = null; 
            document.getElementById('loginPage').style.display = 'block'; 
            document.getElementById('mainApp').style.display = 'none'; 
        }

        function showAlert(message, type = 'success') { 
            const alert = document.getElementById('alertMessage'); 
            alert.className = `alert alert-${type}`; 
            alert.textContent = message; 
            alert.style.display = 'block'; 
            setTimeout(() => { alert.style.display = 'none'; }, 3000); 
        }

        function showPage(pageName) { 
            document.querySelectorAll('.page').forEach(page => page.classList.remove('active-page')); 
            document.getElementById(`${pageName}Page`).classList.add('active-page'); 
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active')); 
            event.target.classList.add('active'); 
            loadPageData(pageName); 
        }

        function loadPageData(pageName) { 
            switch(pageName) { 
                case 'dashboard': loadDashboard(); break; 
                case 'children': loadChildren(); break; 
                case 'groups': loadGroups(); break; 
                case 'trainings': loadTrainings(); loadGroupsForFilter(); break; 
                case 'attendance': loadTrainingsForAttendance(); break; 
                case 'applications': loadApplications(); break; 
                case 'coaches': loadCoaches(); break; 
                case 'transfers': loadTransferRequests(); break; 
            } 
        }

        async function loadAllData() { 
            await Promise.all([loadChildren(), loadGroups(), loadTrainings(), loadCoaches()]); 
        }

        async function loadDashboard() { 
            try { 
                const response = await fetch(`${API_BASE}/dashboard/stats`); 
                const stats = await response.json(); 
                document.getElementById('statsGrid').innerHTML = `
                    <div class="stat-card"><div class="stat-number">${stats.children || 0}</div><div class="stat-label">Детей</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.groups || 0}</div><div class="stat-label">Групп</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.coaches || 0}</div><div class="stat-label">Тренеров</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.trainingsThisMonth || 0}</div><div class="stat-label">Тренировок в месяце</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.attendanceRate || 0}%</div><div class="stat-label">Посещаемость</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.pendingApplications || 0}</div><div class="stat-label">Заявок на рассмотрении</div></div>
                `; 
            } catch (error) { 
                console.error('Error loading dashboard:', error); 
            } 
        }

        async function loadChildren() { 
            try { 
                const response = await fetch(`${API_BASE}/children`); 
                const children = await response.json(); 
                document.getElementById('childrenTableBody').innerHTML = children.map(child => `
                    <tr>
                        <td>${child.id}</td>
                        <td>${child.name}</td>
                        <td>${child.birthdate}</td>
                        <td>${child.class_num || '-'}</td>
                        <td>${child.group_name || 'Не назначен'}</td>
                        <td><span class="status-badge ${child.is_active ? 'status-active' : 'status-completed'}">${child.is_active ? 'Активен' : 'Неактивен'}</span></td>
                        <td>
                            <button class="btn" style="background:#28a745;color:white;padding:5px 10px;" onclick="editChild(${child.id})">✏️</button>
                            <button class="btn" style="background:#dc3545;color:white;padding:5px 10px;" onclick="deleteChild(${child.id})">🗑️</button>
                        </td>
                    </tr>
                `).join(''); 
            } catch (error) { 
                console.error('Error loading children:', error); 
            } 
        }

        async function loadGroups() { 
            try { 
                const response = await fetch(`${API_BASE}/groups`); 
                const groups = await response.json(); 
                document.getElementById('groupsTableBody').innerHTML = groups.map(group => `
                    <tr>
                        <td>${group.id}</td>
                        <td>${group.name}</td>
                        <td>${group.level}</td>
                        <td>${group.coach_name || 'Не назначен'}</td>
                        <td>${group.max_capacity}</td>
                        <td>${group.current_enrollment || 0}/${group.max_capacity}</td>
                        <td>
                            <button class="btn" style="background:#28a745;color:white;padding:5px 10px;" onclick="editGroup(${group.id})">✏️</button>
                            <button class="btn" style="background:#dc3545;color:white;padding:5px 10px;" onclick="deleteGroup(${group.id})">🗑️</button>
                        </td>
                    </tr>
                `).join(''); 
            } catch (error) { 
                console.error('Error loading groups:', error); 
            } 
        }

        async function loadTrainings() { 
            const groupFilter = document.getElementById('trainingGroupFilter')?.value || ''; 
            try { 
                const url = groupFilter ? `${API_BASE}/trainings?group_id=${groupFilter}` : `${API_BASE}/trainings`; 
                const response = await fetch(url); 
                const trainings = await response.json(); 
                document.getElementById('trainingsTableBody').innerHTML = trainings.map(training => `
                    <tr>
                        <td>${training.date}</td>
                        <td>${training.group_name}</td>
                        <td>${training.start_time} - ${training.end_time}</td>
                        <td><span class="status-badge ${training.status === 'scheduled' ? 'status-active' : 'status-completed'}">${training.status === 'scheduled' ? 'Запланирована' : 'Проведена'}</span></td>
                        <td><button class="btn btn-primary" style="padding:5px 10px;" onclick="markAttendance(${training.id})">Отметить посещаемость</button></td>
                    </tr>
                `).join(''); 
            } catch (error) { 
                console.error('Error loading trainings:', error); 
            } 
        }

        async function loadAttendance() { 
            const trainingId = document.getElementById('attendanceTraining').value; 
            if (!trainingId) return; 
            try { 
                const response = await fetch(`${API_BASE}/trainings/${trainingId}/attendance`); 
                const attendance = await response.json(); 
                document.getElementById('attendanceForm').innerHTML = `
                    <h3>Отметка посещаемости</h3>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Ребёнок</th>
                                <th>Статус</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${attendance.map(item => `
                                <tr>
                                    <td>${item.child_name}</td>
                                    <td>
                                        <select onchange="updateAttendance(${trainingId}, ${item.child_id}, this.value)">
                                            <option value="present" ${item.status === 'present' ? 'selected' : ''}>Присутствовал</option>
                                            <option value="absent_sick" ${item.status === 'absent_sick' ? 'selected' : ''}>Отсутствовал (болезнь)</option>
                                            <option value="absent_family" ${item.status === 'absent_family' ? 'selected' : ''}>Отсутствовал (семейные обстоятельства)</option>
                                            <option value="absent_no_reason" ${item.status === 'absent_no_reason' ? 'selected' : ''}>Отсутствовал (без причины)</option>
                                        </select>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    <button class="btn btn-primary" onclick="saveAttendance(${trainingId})">Сохранить</button>
                `; 
            } catch (error) { 
                console.error('Error loading attendance:', error); 
            } 
        }

        async function updateAttendance(trainingId, childId, status) { 
            try { 
                await fetch(`${API_BASE}/attendance`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify({ training_id: trainingId, child_id: childId, status }) 
                }); 
                showAlert('Посещаемость обновлена'); 
            } catch (error) { 
                console.error('Error updating attendance:', error); 
            } 
        }

        function saveAttendance(trainingId) { 
            showAlert('Посещаемость сохранена'); 
        }

        async function loadApplications() { 
            try { 
                const response = await fetch(`${API_BASE}/applications`); 
                const applications = await response.json(); 
                document.getElementById('applicationsTableBody').innerHTML = applications.map(app => `
                    <tr>
                        <td>${app.id}</td>
                        <td>${app.child_name || app.public_child_name || '-'}</td>
                        <td>${app.group_name}</td>
                        <td><span class="status-badge">${getStatusText(app.status)}</span></td>
                        <td>${app.created_at}</td>
                        <td>${(app.status === 'new' || app.status === 'on_review') ? `
                            <button class="btn btn-success" style="padding:5px 10px;" onclick="approveApplication(${app.id})">✅ Одобрить</button>
                            <button class="btn btn-danger" style="padding:5px 10px;" onclick="rejectApplication(${app.id})">❌ Отклонить</button>
                        ` : ''}</td>
                    </tr>
                `).join(''); 
            } catch (error) { 
                console.error('Error loading applications:', error); 
            } 
        }

        async function loadCoaches() { 
            try { 
                const response = await fetch(`${API_BASE}/coaches`); 
                const coaches = await response.json(); 
                document.getElementById('coachesTableBody').innerHTML = coaches.map(coach => `
                    <tr>
                        <td>${coach.id}</td>
                        <td>${coach.name}</td>
                        <td>${coach.email}</td>
                        <td>${coach.phone || '-'}</td>
                        <td>${coach.groups_count || 0}</td>
                        <td>
                            <button class="btn" style="background:#28a745;color:white;padding:5px 10px;" onclick="editCoach(${coach.id})">✏️</button>
                            <button class="btn" style="background:#dc3545;color:white;padding:5px 10px;" onclick="deleteCoach(${coach.id})">🗑️</button>
                        </td>
                    </tr>
                `).join(''); 
                const coachSelect = document.getElementById('groupCoachId'); 
                if (coachSelect) { 
                    coachSelect.innerHTML = '<option value="">Выберите тренера</option>' + coaches.map(coach => `<option value="${coach.id}">${coach.name}</option>`).join(''); 
                } 
            } catch (error) { 
                console.error('Error loading coaches:', error); 
            } 
        }

        async function loadTransferRequests() { 
            try { 
                const response = await fetch(`${API_BASE}/transfer-requests`); 
                const transfers = await response.json(); 
                document.getElementById('transfersTableBody').innerHTML = transfers.map(transfer => `
                    <tr>
                        <td>${transfer.id}</td>
                        <td>${transfer.child_name}</td>
                        <td>${transfer.from_group_name}</td>
                        <td>${transfer.suggested_group_name || 'Не указана'}</td>
                        <td><span class="status-badge">${transfer.status === 'pending' ? 'На рассмотрении' : transfer.status === 'approved' ? 'Одобрен' : 'Отклонён'}</span></td>
                        <td>${transfer.status === 'pending' ? `
                            <button class="btn btn-success" style="padding:5px 10px;" onclick="approveTransfer(${transfer.id})">✅ Одобрить</button>
                            <button class="btn btn-danger" style="padding:5px 10px;" onclick="rejectTransfer(${transfer.id})">❌ Отклонить</button>
                        ` : ''}</td>
                    </tr>
                `).join(''); 

                const children = await fetch(`${API_BASE}/children`).then(r => r.json()); 
                const groups = await fetch(`${API_BASE}/groups`).then(r => r.json()); 
                const childSelect = document.getElementById('transferChildId'); 
                if (childSelect) { 
                    childSelect.innerHTML = children.map(child => `<option value="${child.id}">${child.name}</option>`).join(''); 
                } 
                const fromGroupSelect = document.getElementById('transferFromGroupId'); 
                const toGroupSelect = document.getElementById('transferSuggestedGroupId'); 
                if (fromGroupSelect && toGroupSelect) { 
                    const options = groups.map(group => `<option value="${group.id}">${group.name}</option>`).join(''); 
                    fromGroupSelect.innerHTML = options; 
                    toGroupSelect.innerHTML = '<option value="">Не выбрана</option>' + options; 
                } 
            } catch (error) { 
                console.error('Error loading transfer requests:', error); 
            } 
        }

        async function loadGroupsForFilter() { 
            try { 
                const response = await fetch(`${API_BASE}/groups`); 
                const groups = await response.json(); 
                const filter = document.getElementById('trainingGroupFilter'); 
                filter.innerHTML = '<option value="">Все группы</option>' + groups.map(group => `<option value="${group.id}">${group.name}</option>`).join(''); 
            } catch (error) { 
                console.error('Error loading groups for filter:', error); 
            } 
        }

        async function loadTrainingsForAttendance() { 
            try { 
                const response = await fetch(`${API_BASE}/trainings?status=scheduled`); 
                const trainings = await response.json(); 
                const select = document.getElementById('attendanceTraining'); 
                select.innerHTML = '<option value="">Выберите тренировку</option>' + trainings.map(training => `<option value="${training.id}">${training.date} - ${training.group_name} (${training.start_time})</option>`).join(''); 
            } catch (error) { 
                console.error('Error loading trainings for attendance:', error); 
            } 
        }

        function openChildModal() { 
            document.getElementById('childModalTitle').textContent = 'Добавить ребёнка'; 
            document.getElementById('childForm').reset(); 
            document.getElementById('childId').value = ''; 
            document.getElementById('childModal').style.display = 'flex'; 
        }

        function closeChildModal() { 
            document.getElementById('childModal').style.display = 'none'; 
        }

        async function editChild(id) { 
            try { 
                const response = await fetch(`${API_BASE}/children/${id}`); 
                const child = await response.json(); 
                document.getElementById('childModalTitle').textContent = 'Редактировать ребёнка'; 
                document.getElementById('childId').value = child.id; 
                document.getElementById('childName').value = child.name; 
                document.getElementById('childBirthdate').value = child.birthdate; 
                document.getElementById('childClass').value = child.class_num || ''; 
                document.getElementById('childStudyYear').value = child.study_year || ''; 
                document.getElementById('childMedicalNote').value = child.medical_note || ''; 
                document.getElementById('childModal').style.display = 'flex'; 
            } catch (error) { 
                console.error('Error loading child:', error); 
            } 
        }

        async function saveChild(e) { 
            e.preventDefault(); 
            const id = document.getElementById('childId').value; 
            const data = { 
                name: document.getElementById('childName').value, 
                birthdate: document.getElementById('childBirthdate').value, 
                class_num: parseInt(document.getElementById('childClass').value) || null, 
                study_year: parseInt(document.getElementById('childStudyYear').value) || null, 
                medical_note: document.getElementById('childMedicalNote').value 
            }; 
            try { 
                const url = id ? `${API_BASE}/children/${id}` : `${API_BASE}/children`; 
                const method = id ? 'PUT' : 'POST'; 
                const response = await fetch(url, { 
                    method: method, 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(data) 
                }); 
                if (response.ok) { 
                    showAlert(id ? 'Ребёнок обновлён' : 'Ребёнок добавлен'); 
                    closeChildModal(); 
                    loadChildren(); 
                } 
            } catch (error) { 
                console.error('Error saving child:', error); 
                showAlert('Ошибка при сохранении', 'error'); 
            } 
        }

        async function deleteChild(id) { 
            if (confirm('Вы уверены, что хотите удалить этого ребёнка?')) { 
                try { 
                    await fetch(`${API_BASE}/children/${id}`, { method: 'DELETE' }); 
                    showAlert('Ребёнок удалён'); 
                    loadChildren(); 
                } catch (error) { 
                    console.error('Error deleting child:', error); 
                } 
            } 
        }

        function openGroupModal() { 
            document.getElementById('groupModalTitle').textContent = 'Создать группу'; 
            document.getElementById('groupForm').reset(); 
            document.getElementById('groupId').value = ''; 
            document.getElementById('groupModal').style.display = 'flex'; 
        }

        function closeGroupModal() { 
            document.getElementById('groupModal').style.display = 'none'; 
        }

        async function editGroup(id) { 
            try { 
                const response = await fetch(`${API_BASE}/groups/${id}`); 
                const group = await response.json(); 
                document.getElementById('groupModalTitle').textContent = 'Редактировать группу'; 
                document.getElementById('groupId').value = group.id; 
                document.getElementById('groupName').value = group.name; 
                document.getElementById('groupLevel').value = group.level; 
                document.getElementById('groupCoachId').value = group.coach_id || ''; 
                document.getElementById('groupMaxCapacity').value = group.max_capacity; 
                document.getElementById('groupModal').style.display = 'flex'; 
            } catch (error) { 
                console.error('Error loading group:', error); 
            } 
        }

        async function saveGroup(e) { 
            e.preventDefault(); 
            const id = document.getElementById('groupId').value; 
            const data = { 
                name: document.getElementById('groupName').value, 
                level: parseInt(document.getElementById('groupLevel').value), 
                coach_id: parseInt(document.getElementById('groupCoachId').value) || null, 
                max_capacity: parseInt(document.getElementById('groupMaxCapacity').value) 
            }; 
            try { 
                const url = id ? `${API_BASE}/groups/${id}` : `${API_BASE}/groups`; 
                const method = id ? 'PUT' : 'POST'; 
                const response = await fetch(url, { 
                    method: method, 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(data) 
                }); 
                if (response.ok) { 
                    showAlert(id ? 'Группа обновлена' : 'Группа создана'); 
                    closeGroupModal(); 
                    loadGroups(); 
                } 
            } catch (error) { 
                console.error('Error saving group:', error); 
            } 
        }

        async function deleteGroup(id) { 
            if (confirm('Вы уверены, что хотите удалить эту группу?')) { 
                try { 
                    await fetch(`${API_BASE}/groups/${id}`, { method: 'DELETE' }); 
                    showAlert('Группа удалена'); 
                    loadGroups(); 
                } catch (error) { 
                    console.error('Error deleting group:', error); 
                } 
            } 
        }

        function openCoachModal() { 
            document.getElementById('coachModalTitle').textContent = 'Добавить тренера'; 
            document.getElementById('coachForm').reset(); 
            document.getElementById('coachId').value = ''; 
            document.getElementById('coachModal').style.display = 'flex'; 
        }

        function closeCoachModal() { 
            document.getElementById('coachModal').style.display = 'none'; 
        }

        async function editCoach(id) { 
            try { 
                const response = await fetch(`${API_BASE}/coaches/${id}`); 
                const coach = await response.json(); 
                document.getElementById('coachModalTitle').textContent = 'Редактировать тренера'; 
                document.getElementById('coachId').value = coach.id; 
                document.getElementById('coachName').value = coach.name; 
                document.getElementById('coachEmail').value = coach.email; 
                document.getElementById('coachPhone').value = coach.phone || ''; 
                document.getElementById('coachModal').style.display = 'flex'; 
            } catch (error) { 
                console.error('Error loading coach:', error); 
            } 
        }

        async function saveCoach(e) { 
            e.preventDefault(); 
            const id = document.getElementById('coachId').value; 
            const data = { 
                name: document.getElementById('coachName').value, 
                email: document.getElementById('coachEmail').value, 
                phone: document.getElementById('coachPhone').value, 
                password: document.getElementById('coachPassword').value || undefined 
            }; 
            if (!data.password) delete data.password; 
            try { 
                const url = id ? `${API_BASE}/coaches/${id}` : `${API_BASE}/coaches`; 
                const method = id ? 'PUT' : 'POST'; 
                const response = await fetch(url, { 
                    method: method, 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(data) 
                }); 
                if (response.ok) { 
                    showAlert(id ? 'Тренер обновлён' : 'Тренер добавлен'); 
                    closeCoachModal(); 
                    loadCoaches(); 
                } 
            } catch (error) { 
                console.error('Error saving coach:', error); 
            } 
        }

        async function deleteCoach(id) { 
            if (confirm('Вы уверены, что хотите удалить этого тренера?')) { 
                try { 
                    await fetch(`${API_BASE}/coaches/${id}`, { method: 'DELETE' }); 
                    showAlert('Тренер удалён'); 
                    loadCoaches(); 
                } catch (error) { 
                    console.error('Error deleting coach:', error); 
                } 
            } 
        }

        function openTransferRequestModal() { 
            document.getElementById('transferForm').reset(); 
            document.getElementById('transferModal').style.display = 'flex'; 
        }

        function closeTransferModal() { 
            document.getElementById('transferModal').style.display = 'none'; 
        }

        async function saveTransferRequest(e) { 
            e.preventDefault(); 
            const data = { 
                child_id: parseInt(document.getElementById('transferChildId').value), 
                from_group_id: parseInt(document.getElementById('transferFromGroupId').value), 
                suggested_group_id: parseInt(document.getElementById('transferSuggestedGroupId').value) || null, 
                comment: document.getElementById('transferComment').value 
            }; 
            try { 
                const response = await fetch(`${API_BASE}/transfer-requests`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(data) 
                }); 
                if (response.ok) { 
                    showAlert('Запрос на перевод отправлен'); 
                    closeTransferModal(); 
                    loadTransferRequests(); 
                } 
            } catch (error) { 
                console.error('Error saving transfer request:', error); 
            } 
        }

        async function approveApplication(id) { 
            try { 
                await fetch(`${API_BASE}/applications/${id}/approve`, { method: 'POST' }); 
                showAlert('Заявка одобрена'); 
                loadApplications(); 
            } catch (error) { 
                console.error('Error approving application:', error); 
            } 
        }

        async function rejectApplication(id) { 
            try { 
                await fetch(`${API_BASE}/applications/${id}/reject`, { method: 'POST' }); 
                showAlert('Заявка отклонена'); 
                loadApplications(); 
            } catch (error) { 
                console.error('Error rejecting application:', error); 
            } 
        }

        async function approveTransfer(id) { 
            try { 
                await fetch(`${API_BASE}/transfer-requests/${id}/approve`, { method: 'POST' }); 
                showAlert('Перевод одобрен'); 
                loadTransferRequests(); 
            } catch (error) { 
                console.error('Error approving transfer:', error); 
            } 
        }

        async function rejectTransfer(id) { 
            try { 
                await fetch(`${API_BASE}/transfer-requests/${id}/reject`, { method: 'POST' }); 
                showAlert('Перевод отклонён'); 
                loadTransferRequests(); 
            } catch (error) { 
                console.error('Error rejecting transfer:', error); 
            } 
        }

        function markAttendance(trainingId) { 
            showPage('attendance'); 
            document.getElementById('attendanceTraining').value = trainingId; 
            loadAttendance(); 
        }

        function getStatusText(status) { 
            const statusMap = { 
                'pending_parent_verification': 'Ожидает подтверждения', 
                'new': 'Новая', 
                'on_review': 'На рассмотрении', 
                'approved': 'Одобрена', 
                'rejected': 'Отклонена', 
                'waiting_list': 'Лист ожидания' 
            }; 
            return statusMap[status] || status; 
        }
    </script>
</body>
</html>'''

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

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


#yjdsq afqk