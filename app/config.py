
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

class Settings:
    def __init__(self):
        # Configuración de la aplicación
        self.app_name = os.getenv("APP_NAME", "SST Platform API")
        self.app_version = os.getenv("APP_VERSION", "1.0.0")
        
        # Configuración de base de datos
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        
        # Configuración de CORS
        self.allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        
        # Configuración de directorios
        self.certificate_output_dir = os.getenv("CERTIFICATE_OUTPUT_DIR", "certificates")
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        
        # Configuración de seguridad
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))
        
        # Configuración de email
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")
        
        # Configuración de logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
