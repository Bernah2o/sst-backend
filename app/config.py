
import os
from dotenv import load_dotenv

# Cargar variables de entorno según el entorno
# En desarrollo: .env
# En producción: Variables del sistema o .env.production
# Detectar automáticamente qué archivo usar
env_file = '.env.production' if os.path.exists('.env.production') else '.env'
print(f"[CONFIG] Cargando variables de entorno desde: {env_file}")
# load_dotenv no sobrescribe variables ya existentes en el sistema
load_dotenv(env_file, override=False)

class Settings:
    def __init__(self):
        # Configuración de la aplicación
        self.app_name = os.getenv("APP_NAME", "SST Platform API")
        self.app_version = os.getenv("APP_VERSION", "1.0.0")
        
        # Configuración de base de datos
        # En producción, DATABASE_URL debe estar configurada en el servidor
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Configuración de debug
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Configuración de CORS
        self.allowed_origins = os.getenv("ALLOWED_ORIGINS", os.getenv("REACT_APP_API_URL")).split(",")
        
        # Configuración del frontend
        self.frontend_url = os.getenv("FRONTEND_URL", os.getenv("REACT_APP_API_URL"))
        
        # Configuración de la API del frontend
        self.react_app_api_url = os.getenv("REACT_APP_API_URL")
        
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
        self.email_use_tls = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
        self.email_use_ssl = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
        
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
        # Firebase Storage configuration
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

    def get_firebase_certificate_path(self, certificate_type: str = "general") -> str:
        """
        Genera dinámicamente la ruta de Firebase Storage para certificados basada en el tipo.
        
        Args:
            certificate_type: Tipo de certificado ('attendance', 'course', 'general', etc.)
            
        Returns:
            str: Ruta de Firebase Storage para el tipo de certificado especificado
        """
        base_path = self.firebase_certificates_path
        
        if certificate_type == "attendance":
            return f"{base_path}/attendance"
        elif certificate_type == "course":
            return f"{base_path}/courses"
        elif certificate_type == "completion":
            return f"{base_path}/completion"
        else:
            # Para tipos no especificados, usar la ruta base
            return base_path

settings = Settings()
