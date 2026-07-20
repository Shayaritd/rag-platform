Write-Host "🔧 Final Fix..." -ForegroundColor Yellow

# 1. Update database.py
@'
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

engine = create_engine(
    DATABASE_URL,
    echo=settings.ENV == "local",
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'@ | Out-File -FilePath api/app/core/database.py -Encoding UTF8

# 2. Update env.py
@'
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.core.database import Base
from app.models.user import User

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'@ | Out-File -FilePath alembic_env.py -Encoding UTF8

# 3. Copy files
Write-Host "📦 Copying files..." -ForegroundColor Yellow
docker cp api/app/core/database.py rag-platform-api-1:/app/app/core/database.py
docker cp alembic_env.py rag-platform-api-1:/app/alembic/env.py
docker cp api/app/models/user.py rag-platform-api-1:/app/app/models/user.py

# 4. Fix alembic.ini
Write-Host "🔧 Fixing alembic.ini..." -ForegroundColor Yellow
docker-compose exec api bash -c "sed -i 's|sqlalchemy.url = .*|sqlalchemy.url = postgresql://postgres:postgres@postgres:5432/rag_platform|g' /app/alembic.ini"

# 5. Run migrations
Write-Host "🗄️ Running migrations..." -ForegroundColor Yellow
docker-compose exec api alembic revision --autogenerate -m "create_users_table"
docker-compose exec api alembic upgrade head

# 6. Restart API
Write-Host "🔄 Restarting API..." -ForegroundColor Yellow
docker-compose restart api

Write-Host ""
Write-Host "✅ All fixed!" -ForegroundColor Green
Write-Host "📚 Open API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "🧪 Test registration:" -ForegroundColor Yellow
Write-Host 'curl -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"email\":\"test@test.com\",\"username\":\"testuser\",\"password\":\"test123\"}"' -ForegroundColor Cyan
