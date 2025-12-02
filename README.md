# Plataforma de Capacitaciones SST

Plataforma web completa para gestión de capacitaciones en Seguridad y Salud en el Trabajo (SST), desarrollada con FastAPI (backend) y React (frontend), cumpliendo con la normativa colombiana.

## 🚀 Características Principales

### Módulos Implementados

- **Gestión de Usuarios**: Registro, autenticación JWT, roles y permisos
- **Cursos y Materiales**: Inducción, reinducción, cursos especializados
- **Evaluaciones**: Cuestionarios, pruebas, calificación automática
- **Encuestas**: Formularios personalizables, análisis de resultados
- **Certificados**: Generación automática, verificación pública
- **Asistencia**: Registro presencial y virtual, seguimiento
- **Notificaciones**: Email, SMS, notificaciones programadas
- **Reportes**: Analíticas, exportación PDF/Excel
- **Auditoría**: Logs completos, trazabilidad

### Cumplimiento Legal

- ✅ Ley 1581 de 2012 (Protección de Datos Personales)
- ✅ Decreto 1072 de 2015 (Sistema de Gestión SST)
- ✅ Resolución 0312 de 2019 (Estándares Mínimos SST)

## 🛠️ Tecnologías Utilizadas

### Backend
- **Framework**: Python 3.9+ con FastAPI
- **Base de Datos**: PostgreSQL con SQLAlchemy ORM
- **Autenticación**: JWT OAuth2
- **Validación**: Pydantic
- **Migraciones**: Alembic
- **Servidor**: Uvicorn/Gunicorn
- **Documentación**: Swagger/OpenAPI automática

### Frontend
- **Framework**: React 18+ con TypeScript
- **UI Library**: Material-UI (MUI)
- **Estado**: React Context API
- **Routing**: React Router
- **HTTP Client**: Axios
- **Build Tool**: Create React App

## 📋 Requisitos Previos

- Python 3.9 o superior
- Node.js 16+ y npm
- PostgreSQL 12 o superior
- Poetry (recomendado) o pip
- Git

## 🔧 Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Bernah2o/sst.git
cd sst
```

### 2. Configurar Entorno Virtual

#### Con Poetry (Recomendado)

```bash
# Instalar Poetry si no lo tienes
curl -sSL https://install.python-poetry.org | python3 -

# Instalar dependencias
poetry install

# Activar entorno virtual
poetry shell
```

#### Con pip y virtualenv

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar Base de Datos

#### Instalar PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Windows: Descargar desde https://www.postgresql.org/download/
# macOS: brew install postgresql
```

#### Crear Base de Datos

```sql
-- Conectar como usuario postgres
sudo -u postgres psql

-- Crear base de datos y usuario
CREATE DATABASE sst_platform;
CREATE USER sst_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE sst_platform TO sst_user;
\q
```

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar configuración
nano .env
```

**Configuración mínima requerida:**

```env
# Base de datos
DATABASE_URL=postgresql://sst_user:your_password@localhost:5432/sst_platform

# Seguridad
SECRET_KEY=tu-clave-secreta-muy-segura-aqui

# Email (configurar según tu proveedor)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password
EMAIL_FROM=noreply@tudominio.com
```

### 5. Ejecutar Migraciones

**⚠️ IMPORTANTE**: Las migraciones ahora se ejecutan de forma controlada, no automáticamente.

```bash
# Verificar estado de la base de datos
python migrate.py check

# Ejecutar migraciones (solo cuando sea necesario)
python migrate.py upgrade

# Verificar que se aplicaron correctamente
python migrate.py current

# Para crear nuevas migraciones (desarrollo)
alembic revision --autogenerate -m "Descripción del cambio"

# Luego aplicar con el script controlado
python migrate.py upgrade
```

### 6. Crear Directorios Necesarios

```bash
mkdir -p uploads logs certificates static templates
```

## 🚀 Ejecución

### Desarrollo

#### Backend (Puerto 8000)
```bash
# Navegar al directorio app
cd app

# Con Poetry
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Con pip
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend (Puerto 3000)
```bash
# En una nueva terminal, navegar al directorio frontend
cd frontend

# Instalar dependencias (primera vez)
npm install

# Ejecutar servidor de desarrollo
npm start
```

### Producción

**📖 Para despliegue en producción, consulta la [Guía de Despliegue](DEPLOYMENT.md)**

```bash
# Despliegue con Docker Compose (Recomendado)
# 1. Ejecutar migraciones de forma controlada
docker-compose --profile migration up migrate

# 2. Levantar la aplicación
docker-compose up -d app

# Despliegue manual
# Backend con Gunicorn
cd app
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**⚠️ Importante**: 
- Las migraciones NO se ejecutan automáticamente
- Usar `python migrate.py` para control manual
- Consultar [DEPLOYMENT.md](DEPLOYMENT.md) para proceso completo

## 🔎 Logging

El backend ajusta el nivel de logging según el entorno:

- Producción: silencioso por defecto (`root` en `ERROR`), `uvicorn.access` deshabilitado.
- Desarrollo: `DEBUG` habilitado para depuración.

Variables de entorno relevantes:

```env
# Entorno (local|development|dev|production)
ENVIRONMENT=production

# Forzar modo debug en desarrollo
DEBUG=false

# Nivel explícito de logging (opcional). Si no se define en producción, se usa ERROR.
LOG_LEVEL=INFO
```

Ejemplos:

- Ver logs de depuración en desarrollo:
```env
ENVIRONMENT=development
DEBUG=true
```

- Mantener producción silenciosa (solo errores):
```env
ENVIRONMENT=production
DEBUG=false
# LOG_LEVEL sin definir (usa ERROR por defecto)
```

## 📚 Uso de la Aplicación

### Acceso a la Aplicación

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints Principales

#### Autenticación

```bash
# Registro de usuario
POST /api/v1/auth/register
{
  "email": "usuario@ejemplo.com",
  "username": "usuario",
  "password": "password123",
  "first_name": "Juan",
  "last_name": "Pérez",
  "document_type": "CC",
  "document_number": "12345678"
}

# Login
POST /api/v1/auth/login
{
  "username": "usuario",
  "password": "password123"
}
```

#### Cursos

```bash
# Listar cursos
GET /api/v1/courses/

# Crear curso (requiere rol trainer/admin)
POST /api/v1/courses/
{
  "title": "Curso de Inducción SST",
  "description": "Curso básico de seguridad",
  "course_type": "induction",
  "duration_hours": 8,
  "is_mandatory": true
}
```

#### Evaluaciones

```bash
# Tomar evaluación
POST /api/v1/evaluations/{evaluation_id}/start

# Enviar respuestas
POST /api/v1/evaluations/{evaluation_id}/submit
{
  "answers": [
    {
      "question_id": 1,
      "selected_answer_ids": ["1", "3"]
    }
  ]
}
```

## 🔐 Roles y Permisos

### Roles Disponibles

- **Admin**: Acceso completo al sistema
- **Trainer**: Crear y gestionar cursos, evaluaciones
- **Supervisor**: Ver reportes, gestionar empleados
- **Employee**: Tomar cursos y evaluaciones

### Matriz de Permisos

| Recurso      | Admin | Trainer | Supervisor | Employee    |
| ------------ | ----- | ------- | ---------- | ----------- |
| Usuarios     | CRUD  | R       | RU         | R (propio)  |
| Cursos       | CRUD  | CRUD    | R          | R           |
| Evaluaciones | CRUD  | CRUD    | R          | R/Submit    |
| Reportes     | R     | R       | R          | -           |
| Certificados | CRUD  | CR      | R          | R (propios) |

## 📊 Estructura del Proyecto

```
sst/
├── app/                    # Backend (FastAPI)
│   ├── api/               # Endpoints de la API
│   │   ├── auth.py        # Autenticación
│   │   ├── users.py       # Gestión de usuarios
│   │   ├── courses.py     # Cursos
│   │   └── ...
│   ├── models/            # Modelos SQLAlchemy
│   │   ├── user.py
│   │   ├── course.py
│   │   └── ...
│   ├── schemas/           # Esquemas Pydantic
│   │   ├── user.py
│   │   ├── course.py
│   │   └── ...
│   ├── services/          # Lógica de negocio
│   │   ├── auth.py
│   │   ├── user.py
│   │   └── ...
│   ├── config.py          # Configuración
│   ├── database.py        # Configuración DB
│   ├── dependencies.py    # Dependencias FastAPI
│   └── main.py           # Aplicación principal
├── frontend/              # Frontend (React)
│   ├── public/           # Archivos públicos
│   ├── src/              # Código fuente React
│   │   ├── components/   # Componentes reutilizables
│   │   ├── pages/        # Páginas de la aplicación
│   │   ├── services/     # Servicios API
│   │   ├── contexts/     # Contextos React
│   │   ├── types/        # Tipos TypeScript
│   │   └── App.tsx       # Componente principal
│   ├── package.json      # Dependencias Node.js
│   └── tsconfig.json     # Configuración TypeScript
├── alembic/              # Migraciones de BD
├── uploads/              # Archivos subidos
├── certificates/         # Certificados generados
├── logs/                 # Logs de aplicación
├── pyproject.toml        # Configuración Poetry
├── alembic.ini          # Configuración Alembic
└── README.md            # Este archivo
```

## 🧪 Pruebas

### Backend
```bash
cd app
# Ejecutar todas las pruebas
pytest

# Ejecutar con cobertura
pytest --cov=app

# Ejecutar pruebas específicas
pytest tests/test_auth.py
```

### Frontend
```bash
cd frontend
# Ejecutar pruebas
npm test

# Ejecutar con cobertura
npm run test:coverage

# Ejecutar pruebas en modo watch
npm test -- --watch
```

## 📈 Monitoreo y Logs

### Logs

- Los logs se guardan en `logs/app.log`
- Configuración de nivel en variable `LOG_LEVEL`
- Rotación automática recomendada en producción

### Health Check

```bash
GET /health
```

### Métricas

- Tiempo de respuesta en header `X-Process-Time`
- Logs de requests/responses
- Auditoría completa en base de datos

## 🐳 Docker

### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

COPY . .

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: "3.8"
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/sst_platform
    depends_on:
      - db

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=sst_platform
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 🔒 Seguridad

### Implementado

- Autenticación JWT con refresh tokens
- Hashing de contraseñas con bcrypt
- Validación de entrada con Pydantic
- CORS configurado
- Rate limiting (recomendado implementar)
- Logs de auditoría completos

### Recomendaciones Adicionales

- Usar HTTPS en producción
- Configurar firewall
- Implementar rate limiting
- Monitoreo de seguridad
- Backups automáticos

## 📝 Contribución

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🆘 Soporte

Para soporte técnico:

- Crear issue en GitHub
- Email: soporte@tudominio.com
- Documentación: `/docs`

## 🔄 Changelog

### v1.0.0 (2024-01-XX)

- ✅ Implementación inicial
- ✅ Módulos de usuarios, cursos, evaluaciones
- ✅ Autenticación JWT
- ✅ API REST completa
- ✅ Documentación Swagger
- ✅ Cumplimiento normativo colombiano

---

**Desarrollado con ❤️ para mejorar la seguridad y salud en el trabajo**
