# PoolCRM
 
PoolCRM/
├── __init__.py
├── main.py     # Web/API endpoints
├── config.py
├── database.py
├── models.py          # все модели SQLAlchemy (~300 строк)
├── auth.py            # JWT + зависимости + хэши
│
├── helpers/             # только бизнес-логика, без эндпоинтов
│   ├── __init__.py
│   ├── training.py      # generate_trainings, get_or_create
│   ├── attendance.py    # mark, statistics, calculate_rate
│   ├── applications.py  # process_application, create_account
│   ├── notifications.py # send_vk, send_email
│   └── transfers.py     # complete_academic_year, transfer_child
│
├── templates/
├── static/
└── run.py
