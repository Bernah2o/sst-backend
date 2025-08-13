# Configuración de Usuario Administrador - Sistema SST

Este documento explica cómo crear usuarios administradores en el sistema SST.

## Scripts Disponibles

### 1. `create_default_admin.py` - Administrador por Defecto

Crea un usuario administrador con credenciales predefinidas, ideal para configuración inicial o desarrollo.

**Credenciales por defecto:**
- **Email:** admin@sst.com
- **Usuario:** admin
- **Contraseña:** Admin123!
- **Rol:** ADMIN

**Uso:**
```bash
# Activar el entorno virtual
env\Scripts\activate

# Ejecutar el script
python create_default_admin.py
```

### 2. `create_admin.py` - Administrador Personalizado

Crea un usuario administrador con datos personalizados ingresados interactivamente.

**Uso:**
```bash
# Activar el entorno virtual
env\Scripts\activate

# Ejecutar el script
python create_admin.py
```

El script solicitará:
- Email
- Nombre de usuario
- Nombre y apellido
- Número de documento
- Contraseña (debe cumplir con los requisitos de seguridad)
- Teléfono (opcional)
- Departamento (opcional)
- Cargo (opcional)

**Requisitos de contraseña:**
- Mínimo 8 caracteres
- Al menos una letra (a-z, A-Z)
- Al menos un número (0-9)
- Al menos un carácter especial (!@#$%^&*(),.?":{}|<>)

## Permisos del Usuario Administrador

Un usuario con rol `ADMIN` puede:

✅ **Gestión de Usuarios**
- Ver, crear, editar y eliminar usuarios
- Cambiar roles de otros usuarios
- Gestionar perfiles de trabajadores

✅ **Gestión de Cursos**
- Crear, editar y eliminar cursos
- Gestionar módulos y materiales
- Asignar instructores

✅ **Reportes y Análisis**
- Ver todos los reportes del sistema
- Exportar datos
- Análisis de progreso y asistencia

✅ **Configuración del Sistema**
- Acceder a configuraciones administrativas
- Gestionar notificaciones
- Configurar parámetros del sistema

✅ **Gestión de Evaluaciones**
- Crear y gestionar evaluaciones
- Ver resultados de todos los usuarios
- Generar certificados

## Verificación del Usuario Creado

Para verificar que el usuario administrador se creó correctamente:

1. **Iniciar sesión en el sistema:**
   - Ir a la aplicación web
   - Usar las credenciales del administrador
   - Verificar que aparezcan las opciones administrativas

2. **Verificar en la base de datos:**
```python
# Script de verificación
from app.database import engine
from app.models.user import User, UserRole
from sqlalchemy.orm import Session

db = Session(engine)
admins = db.query(User).filter(User.role == UserRole.ADMIN).all()

print("Usuarios administradores:")
for admin in admins:
    print(f"- {admin.username} ({admin.email}) - ID: {admin.id}")

db.close()
```

## Seguridad

⚠️ **Importante:**

1. **Cambiar contraseña por defecto:** Si usas `create_default_admin.py`, cambia la contraseña `Admin123!` inmediatamente después del primer inicio de sesión.

2. **Requisitos de contraseña:** Todas las contraseñas deben cumplir con los siguientes requisitos:
   - Mínimo 8 caracteres
   - Al menos una letra (a-z, A-Z)
   - Al menos un número (0-9)
   - Al menos un carácter especial (!@#$%^&*(),.?":{}|<>)

3. **Limitar acceso:** Solo crea usuarios administradores cuando sea necesario.

4. **Auditoría:** El sistema registra las acciones de los administradores en los logs de auditoría.

## Solución de Problemas

### Error: "Ya existe un usuario con ese email/usuario"
- Verifica si ya existe un usuario con esos datos
- Usa credenciales diferentes
- Si es necesario, elimina el usuario existente desde la base de datos

### Error de conexión a la base de datos
- Verifica que la base de datos esté ejecutándose
- Confirma la configuración en el archivo `.env`
- Asegúrate de que las migraciones estén aplicadas

### Error de importación de módulos
- Verifica que el entorno virtual esté activado
- Ejecuta el script desde el directorio raíz del proyecto
- Instala las dependencias: `pip install -r requirements.txt`

## Comandos Útiles

```bash
# Crear administrador por defecto
python create_default_admin.py

# Crear administrador personalizado
python create_admin.py

# Verificar usuarios en la base de datos
python -c "from app.database import engine; from app.models.user import User; from sqlalchemy.orm import Session; db = Session(engine); users = db.query(User).all(); [print(f'{u.username} - {u.role.value}') for u in users]; db.close()"

# Ver solo administradores
python -c "from app.database import engine; from app.models.user import User, UserRole; from sqlalchemy.orm import Session; db = Session(engine); admins = db.query(User).filter(User.role == UserRole.ADMIN).all(); [print(f'{a.username} ({a.email})') for a in admins]; db.close()"
```

---

**Nota:** Estos scripts deben ejecutarse con el entorno virtual activado y desde el directorio raíz del proyecto.