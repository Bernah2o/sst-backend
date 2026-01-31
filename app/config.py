
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
        
        # Configuración de Contabo Object Storage (S3 compatible)
        # Soporte para ambas convenciones de nombres (CONTABO_* y CONTABO_S3_*)
        self.use_contabo_storage = (
            os.getenv("USE_CONTABO_STORAGE", "False").lower() == "true" or 
            os.getenv("STORAGE_PROVIDER", "").lower() == "contabo"
        )
        
        self.contabo_endpoint_url = os.getenv("CONTABO_ENDPOINT_URL", os.getenv("CONTABO_S3_ENDPOINT"))
        self.contabo_access_key_id = os.getenv("CONTABO_ACCESS_KEY_ID", os.getenv("CONTABO_S3_ACCESS_KEY_ID"))
        self.contabo_secret_access_key = os.getenv("CONTABO_SECRET_ACCESS_KEY", os.getenv("CONTABO_S3_SECRET_ACCESS_KEY"))
        self.contabo_bucket_name = os.getenv("CONTABO_BUCKET_NAME", os.getenv("CONTABO_S3_BUCKET"))
        self.contabo_region = os.getenv("CONTABO_REGION", os.getenv("CONTABO_S3_REGION", "default"))
        
        # URL publica base
        public_base_url = os.getenv("CONTABO_PUBLIC_BASE_URL", os.getenv("CONTABO_S3_PUBLIC_BASE_URL"))
        if not public_base_url and self.contabo_endpoint_url and self.contabo_bucket_name:
             # Construir URL por defecto si no se proporciona
             public_base_url = f"{self.contabo_endpoint_url.rstrip('/')}/{self.contabo_bucket_name}"
             
        self.contabo_public_base_url = public_base_url
        self.contabo_make_public = os.getenv("CONTABO_MAKE_PUBLIC", "True").lower() == "true"

        # Configuración de Perplexity AI
        # Modelos disponibles: sonar, sonar-pro, sonar-reasoning
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        self.perplexity_model = os.getenv("PERPLEXITY_MODEL", "sonar")

settings = Settings()
