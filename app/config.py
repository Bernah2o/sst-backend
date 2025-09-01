
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env.production
load_dotenv('.env.production')

class Settings:
    def __init__(self):
        # Configuración de la aplicación
        self.app_name = os.getenv("APP_NAME", "SST Platform API")
        self.app_version = os.getenv("APP_VERSION", "1.0.0")
        
        # Configuración de base de datos
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.debug = os.getenv("DEBUG", "False").lower() == "false"
        
        # Configuración de CORS
        self.allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        
        # Configuración del frontend
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        # Configuración de directorios
        self.certificate_output_dir = os.getenv("CERTIFICATE_OUTPUT_DIR", "certificates")
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        
        # Configuración de seguridad
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 120))
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))
        
        # Configuración de email
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")
        
        # Configuración de logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # Configuración de Firebase Storage
        self.gs_bucket_name = os.getenv("GS_BUCKET_NAME")
        self.firebase_storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        self.firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
        self.firebase_static_path = os.getenv("FIREBASE_STATIC_PATH", "fastapi_project/static")
        self.firebase_uploads_path = os.getenv("FIREBASE_UPLOADS_PATH", "fastapi_project/uploads")
        self.firebase_certificates_path = os.getenv("FIREBASE_CERTIFICATES_PATH", "fastapi_project/certificates")
        self.firebase_medical_reports_path = os.getenv("FIREBASE_MEDICAL_REPORTS_PATH", "fastapi_project/medical_reports")
        self.firebase_attendance_lists_path = os.getenv("FIREBASE_ATTENDANCE_LISTS_PATH", "fastapi_project/attendance_lists")
        self.use_firebase_storage = os.getenv("USE_FIREBASE_STORAGE", "False").lower() == "true"
        self.firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        
        # Variables de entorno individuales de Firebase (alternativa al archivo JSON)
        self.firebase_type = os.getenv("FIREBASE_TYPE")
        self.firebase_private_key_id = os.getenv("FIREBASE_PRIVATE_KEY_ID")
        self.firebase_private_key = os.getenv("FIREBASE_PRIVATE_KEY")
        self.firebase_client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
        self.firebase_client_id = os.getenv("FIREBASE_CLIENT_ID")
        self.firebase_auth_uri = os.getenv("FIREBASE_AUTH_URI")
        self.firebase_token_uri = os.getenv("FIREBASE_TOKEN_URI")
        self.firebase_auth_provider_x509_cert_url = os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL")
        self.firebase_client_x509_cert_url = os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
        self.firebase_universe_domain = os.getenv("FIREBASE_UNIVERSE_DOMAIN")

settings = Settings()
