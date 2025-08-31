# Configuración de Firebase Storage

## 🎯 Propósito

**Firebase Storage es EXCLUSIVAMENTE para PRODUCCIÓN**. En desarrollo local se utilizan carpetas del sistema de archivos.

## 📁 Configuración por Entorno

### Desarrollo Local
- **Almacenamiento**: Carpetas locales (`uploads/`, `certificates/`, etc.)
- **Firebase Storage**: DESHABILITADO (`USE_FIREBASE_STORAGE=False`)
- **Variables Firebase**: NO REQUERIDAS

### Producción
- **Almacenamiento**: Firebase Storage
- **Firebase Storage**: HABILITADO (`USE_FIREBASE_STORAGE=True`)
- **Variables Firebase**: 21 variables requeridas (sin archivo JSON)

## ¿Por qué 21 variables en lugar de 15?

El archivo `firebase-credentials.json` contiene todas las credenciales del service account de Firebase. Para reemplazarlo completamente con variables de entorno individuales, necesitas extraer todos los campos del JSON y configurarlos como variables separadas.

## Variables de Entorno Requeridas (21 total)

### Variables Básicas de Firebase Storage (3)
```bash
FIREBASE_STORAGE_BUCKET=dh2ocol-cc47f.appspot.com
FIREBASE_PROJECT_ID=dh2ocol-cc47f
USE_FIREBASE_STORAGE=True
```

### Credenciales de Service Account (11)
```bash
FIREBASE_TYPE=service_account
FIREBASE_PRIVATE_KEY_ID=eec7239f6c77376959d8a024161bb80440cd1cbe
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n[CLAVE_PRIVADA_COMPLETA]\n-----END PRIVATE KEY-----"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-vyy98@dh2ocol-cc47f.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=113154789548406190763
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-vyy98%40dh2ocol-cc47f.iam.gserviceaccount.com
FIREBASE_UNIVERSE_DOMAIN=googleapis.com
```

### Variables Opcionales de Configuración (7)
```bash
GS_BUCKET_NAME=dh2ocol-cc47f.appspot.com
FIREBASE_STATIC_PATH=fastapi_project/static
FIREBASE_UPLOADS_PATH=fastapi_project/uploads
FIREBASE_CERTIFICATES_PATH=fastapi_project/certificates
FIREBASE_MEDICAL_REPORTS_PATH=fastapi_project/medical_reports
FIREBASE_ATTENDANCE_LISTS_PATH=fastapi_project/attendance_lists
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json  # Solo para desarrollo local
```

## ¿Por qué `FIREBASE_CREDENTIALS_PATH` apunta a un archivo en .gitignore?

El archivo `firebase-credentials.json` está en `.gitignore` porque:

1. **Contiene credenciales sensibles** que no deben subirse al repositorio
2. **Es solo para desarrollo local** - en producción usas variables de entorno
3. **Evita exponer claves privadas** en el código fuente

## Configuración por Entorno

### 🏠 Desarrollo Local
- ✅ **USE_FIREBASE_STORAGE=False** (o no configurar)
- ✅ Usa carpetas locales: `uploads/`, `certificates/`, `medical_reports/`, etc.
- ✅ **NO necesitas** las 21 variables de Firebase
- ✅ **NO necesitas** el archivo `firebase-credentials.json`
- ✅ Almacenamiento en sistema de archivos local

### 🚀 Producción (Render)

#### Opción 1: Variables de Entorno Individuales (Recomendado)
- ✅ **USE_FIREBASE_STORAGE=True**
- ✅ **21 variables de entorno** (como se muestra arriba)
- ✅ No necesitas subir archivos JSON
- ✅ Más seguro
- ✅ Fácil de gestionar en plataformas como Render

#### Opción 2: Archivo JSON en Producción (No Recomendado)
- ❌ Subir `firebase-credentials.json` al servidor
- ❌ Gestionar archivos sensibles
- ❌ Menos seguro
- ❌ Más complejo de desplegar

#### Opción 3: Credenciales por Defecto de Google Cloud
- ⚠️ Solo funciona si despliegas en Google Cloud Platform
- ⚠️ No funciona en Render, Heroku, etc.

## Configuración Recomendada para Render

1. **Copia todas las 21 variables** de tu archivo `.env` local
2. **Pega las variables** en la configuración de Render
3. **NO subas** el archivo `firebase-credentials.json`
4. **Verifica** que `USE_FIREBASE_STORAGE=True`

## Validación

Puedes usar el script `test_firebase_env_config.py` para validar tu configuración:

```bash
python test_firebase_env_config.py
```

## Notas Importantes

- **FIREBASE_PRIVATE_KEY**: Debe incluir `\n` para los saltos de línea
- **Todas las 11 credenciales** son obligatorias para que funcione
- **Las 7 variables opcionales** tienen valores por defecto si no las configuras
- **El archivo JSON** solo se usa si las variables de entorno no están disponibles

## Conclusión

### Para Desarrollo Local:
- **0 variables de Firebase** necesarias
- Usa `USE_FIREBASE_STORAGE=False` o no configures la variable
- Los archivos se guardan en carpetas locales

### Para Producción:
- **21 variables de entorno** para una configuración completa de Firebase Storage
- Usa `USE_FIREBASE_STORAGE=True`
- Los archivos se guardan en Firebase Storage

**La confusión viene porque algunas variables son opcionales y tienen valores por defecto, pero para una configuración robusta y completa en producción, se recomienda configurar todas las 21 variables.**

### Flujo de Trabajo Recomendado:
1. **Desarrollo**: Trabaja con almacenamiento local (carpetas)
2. **Producción**: Configura Firebase Storage con las 21 variables
3. **Testing**: Puedes probar Firebase localmente configurando las variables