"""Migracion manual - tablas contractors y modificaciones

Revision ID: fee1d228404b
Revises: 768f9dbc520d
Create Date: 2025-10-02 00:25:53.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fee1d228404b'
down_revision = '768f9dbc520d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get database connection
    conn = op.get_bind()
    
    # Check if tables exist
    existing_tables_result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)).fetchall()
    existing_tables = [row[0] for row in existing_tables_result]
    
    # Check if ENUM types exist
    existing_types_result = conn.execute(sa.text("""
        SELECT typname FROM pg_type WHERE typtype = 'e'
    """)).fetchall()
    existing_type_names = [row[0] for row in existing_types_result]
    
    # Create ENUM types if they don't exist
    enum_types = {
        'gender': "('MALE', 'FEMALE', 'OTHER')",
        'documenttype': "('CEDULA', 'PASSPORT', 'OTHER', 'SPECIAL_PERMIT')",
        'contracttype': "('SERVICES', 'WORK_LABOR', 'CONSULTING', 'TEMPORARY')",
        'workmodality': "('ON_SITE', 'REMOTE', 'TELEWORK', 'HOME_OFFICE', 'MOBILE')",
        'risklevel': "('LEVEL_I', 'LEVEL_II', 'LEVEL_III', 'LEVEL_IV', 'LEVEL_V')",
        'bloodtype': "('A_POSITIVE', 'A_NEGATIVE', 'B_POSITIVE', 'B_NEGATIVE', 'AB_POSITIVE', 'AB_NEGATIVE', 'O_POSITIVE', 'O_NEGATIVE')",
        'userrole': "('ADMIN', 'TRAINER', 'EMPLOYEE', 'SUPERVISOR')"
    }
    
    for enum_name, enum_values in enum_types.items():
        if enum_name not in existing_type_names:
            conn.execute(sa.text(f"CREATE TYPE {enum_name} AS ENUM {enum_values}"))
    
    # Create contractors table if it doesn't exist
    if 'contractors' not in existing_tables:
        conn.execute(sa.text("""
            CREATE TABLE contractors (
                id SERIAL PRIMARY KEY,
                photo VARCHAR(255),
                gender gender NOT NULL,
                document_type documenttype NOT NULL,
                document_number VARCHAR(50) NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                birth_date DATE NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                contract_type contracttype NOT NULL,
                work_modality workmodality,
                profession VARCHAR(100),
                risk_level risklevel NOT NULL,
                position VARCHAR(100) NOT NULL,
                occupation VARCHAR(100),
                contract_value NUMERIC(12, 2),
                fecha_de_inicio DATE,
                fecha_de_finalizacion DATE,
                area_id INTEGER,
                eps VARCHAR(100),
                afp VARCHAR(100),
                arl VARCHAR(100),
                country VARCHAR(100),
                department VARCHAR(100),
                city VARCHAR(100),
                direccion VARCHAR(255),
                blood_type bloodtype,
                certificacion_arl_url VARCHAR(500),
                certificacion_eps_url VARCHAR(500),
                certificacion_afp_url VARCHAR(500),
                otros_documentos_url TEXT,
                certificacion_arl_key VARCHAR(500),
                certificacion_eps_key VARCHAR(500),
                certificacion_afp_key VARCHAR(500),
                otros_documentos_keys TEXT,
                observations TEXT,
                is_active BOOLEAN NOT NULL,
                assigned_role userrole NOT NULL,
                is_registered BOOLEAN NOT NULL,
                user_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (area_id) REFERENCES areas(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))
        
        # Create indexes
        conn.execute(sa.text("CREATE INDEX ix_contractors_id ON contractors(id)"))
        conn.execute(sa.text("CREATE INDEX ix_contractors_email ON contractors(email)"))
        conn.execute(sa.text("CREATE INDEX ix_contractors_document_number ON contractors(document_number)"))
    
    # Create contractor_contracts table if it doesn't exist
    if 'contractor_contracts' not in existing_tables:
        conn.execute(sa.text("""
            CREATE TABLE contractor_contracts (
                id SERIAL PRIMARY KEY,
                contractor_id INTEGER NOT NULL,
                contract_number VARCHAR(100) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                contract_value NUMERIC(12, 2),
                description TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (contractor_id) REFERENCES contractors(id)
            )
        """))
        
        conn.execute(sa.text("CREATE INDEX ix_contractor_contracts_id ON contractor_contracts(id)"))
    
    # Create contractor_documents table if it doesn't exist
    if 'contractor_documents' not in existing_tables:
        conn.execute(sa.text("""
            CREATE TABLE contractor_documents (
                id SERIAL PRIMARY KEY,
                contractor_id INTEGER NOT NULL,
                document_name VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER,
                content_type VARCHAR(100),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (contractor_id) REFERENCES contractors(id)
            )
        """))
        
        conn.execute(sa.text("CREATE INDEX ix_contractor_documents_id ON contractor_documents(id)"))
    
    # Check if contractor_id column exists in enrollments
    enrollments_columns_result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'enrollments' AND table_schema = 'public'
    """)).fetchall()
    enrollments_columns = [row[0] for row in enrollments_columns_result]
    
    # Add contractor_id column to enrollments if it doesn't exist
    if 'contractor_id' not in enrollments_columns:
        conn.execute(sa.text("ALTER TABLE enrollments ADD COLUMN contractor_id INTEGER"))
        conn.execute(sa.text("ALTER TABLE enrollments ADD FOREIGN KEY (contractor_id) REFERENCES contractors(id)"))
    
    # Check if user_id column in enrollments allows NULL
    user_id_nullable_result = conn.execute(sa.text("""
        SELECT is_nullable FROM information_schema.columns 
        WHERE table_name = 'enrollments' AND column_name = 'user_id' AND table_schema = 'public'
    """)).fetchone()
    
    if user_id_nullable_result and user_id_nullable_result[0] == 'NO':
        conn.execute(sa.text("ALTER TABLE enrollments ALTER COLUMN user_id DROP NOT NULL"))
    
    # Modify users table columns if needed
    users_columns_result = conn.execute(sa.text("""
        SELECT column_name, is_nullable, column_default FROM information_schema.columns 
        WHERE table_name = 'users' AND table_schema = 'public'
        AND column_name IN ('failed_login_attempts', 'account_locked_until', 'last_failed_login')
    """)).fetchall()
    
    users_columns_info = {row[0]: {'nullable': row[1], 'default': row[2]} for row in users_columns_result}
    
    # Modify failed_login_attempts to remove default if it exists
    if 'failed_login_attempts' in users_columns_info:
        if users_columns_info['failed_login_attempts']['default'] is not None:
            conn.execute(sa.text("ALTER TABLE users ALTER COLUMN failed_login_attempts DROP DEFAULT"))
    
    # Modify timestamp columns to use TIMESTAMP instead of TIMESTAMPTZ
    for col_name in ['account_locked_until', 'last_failed_login']:
        if col_name in users_columns_info:
            # Check current data type
            data_type_result = conn.execute(sa.text(f"""
                SELECT data_type FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = '{col_name}' AND table_schema = 'public'
            """)).fetchone()
            
            if data_type_result and 'timestamp with time zone' in data_type_result[0].lower():
                conn.execute(sa.text(f"ALTER TABLE users ALTER COLUMN {col_name} TYPE TIMESTAMP"))


def downgrade() -> None:
    # Get database connection
    conn = op.get_bind()
    
    # Check if tables exist
    existing_tables_result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)).fetchall()
    existing_tables = [row[0] for row in existing_tables_result]
    
    # Revert users table changes
    users_columns_result = conn.execute(sa.text("""
        SELECT column_name, data_type FROM information_schema.columns 
        WHERE table_name = 'users' AND table_schema = 'public'
        AND column_name IN ('failed_login_attempts', 'account_locked_until', 'last_failed_login')
    """)).fetchall()
    
    users_columns_info = {row[0]: row[1] for row in users_columns_result}
    
    # Revert timestamp columns
    for col_name in ['account_locked_until', 'last_failed_login']:
        if col_name in users_columns_info and 'timestamp without time zone' in users_columns_info[col_name].lower():
            conn.execute(sa.text(f"ALTER TABLE users ALTER COLUMN {col_name} TYPE TIMESTAMP WITH TIME ZONE"))
    
    # Restore default for failed_login_attempts
    if 'failed_login_attempts' in users_columns_info:
        conn.execute(sa.text("ALTER TABLE users ALTER COLUMN failed_login_attempts SET DEFAULT 0"))
    
    # Check if enrollments table exists and has the columns
    if 'enrollments' in existing_tables:
        enrollments_columns_result = conn.execute(sa.text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'enrollments' AND table_schema = 'public'
        """)).fetchall()
        enrollments_columns = [row[0] for row in enrollments_columns_result]
        
        # Drop foreign key constraint for contractor_id
        if 'contractor_id' in enrollments_columns:
            # Find and drop the foreign key constraint
            fk_result = conn.execute(sa.text("""
                SELECT constraint_name FROM information_schema.table_constraints 
                WHERE table_name = 'enrollments' AND constraint_type = 'FOREIGN KEY'
                AND constraint_name LIKE '%contractor%'
            """)).fetchall()
            
            for fk in fk_result:
                conn.execute(sa.text(f"ALTER TABLE enrollments DROP CONSTRAINT {fk[0]}"))
        
        # Make user_id NOT NULL again
        if 'user_id' in enrollments_columns:
            user_id_nullable_result = conn.execute(sa.text("""
                SELECT is_nullable FROM information_schema.columns 
                WHERE table_name = 'enrollments' AND column_name = 'user_id' AND table_schema = 'public'
            """)).fetchone()
            
            if user_id_nullable_result and user_id_nullable_result[0] == 'YES':
                conn.execute(sa.text("ALTER TABLE enrollments ALTER COLUMN user_id SET NOT NULL"))
        
        # Drop contractor_id column
        if 'contractor_id' in enrollments_columns:
            conn.execute(sa.text("ALTER TABLE enrollments DROP COLUMN contractor_id"))
    
    # Drop tables if they exist
    for table_name in ['contractor_documents', 'contractor_contracts', 'contractors']:
        if table_name in existing_tables:
            conn.execute(sa.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))