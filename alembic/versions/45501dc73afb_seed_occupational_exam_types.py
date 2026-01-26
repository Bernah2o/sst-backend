"""seed_occupational_exam_types

Revision ID: 45501dc73afb
Revises: 79d7a5617d8f
Create Date: 2026-01-22 21:40:42.373811

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Boolean, Text

# revision identifiers, used by Alembic.
revision = '45501dc73afb'
down_revision = '79d7a5617d8f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Definir la tabla temporalmente para la inserción
    tipos_examen_table = table(
        'tipos_examen',
        column('nombre', String),
        column('descripcion', Text),
        column('activo', Boolean)
    )

    # Datos a insertar
    # Mapeo del Enum ExamType a nombres legibles
    data_to_insert = [
        {"nombre": "Examen de Ingreso", "descripcion": "Evaluación médica de ingreso (examen_ingreso)", "activo": True},
        {"nombre": "Examen Periódico", "descripcion": "Evaluación médica periódica (examen_periodico)", "activo": True},
        {"nombre": "Examen de Reintegro", "descripcion": "Evaluación médica de reintegro (examen_reintegro)", "activo": True},
        {"nombre": "Examen de Retiro", "descripcion": "Evaluación médica de retiro (examen_retiro)", "activo": True},
    ]

    # Insertar datos si no existen (la unicidad de 'nombre' debería manejarse, pero aquí hacemos insert selectivo o try/except conceptual)
    # Como SQLALchemy Core insert no tiene "ON CONFLICT DO NOTHING" portable fácilmente en todos los dialectos sin dialect-specific imports,
    # y alembic suele ser agnóstico, haremos una verificación simple o dejaremos que falle si ya existen (pero mejor verificar).
    
    # Para simplicidad en migración de datos, usaremos op.execute con SQL puro o connection.
    connection = op.get_bind()
    
    for item in data_to_insert:
        # Verificar si existe
        exists = connection.execute(
            sa.text("SELECT 1 FROM tipos_examen WHERE nombre = :nombre"),
            {"nombre": item["nombre"]}
        ).scalar()
        
        if not exists:
            op.bulk_insert(tipos_examen_table, [item])


def downgrade() -> None:
    # Opcional: Eliminar los datos insertados
    connection = op.get_bind()
    names = [
        "Examen de Ingreso",
        "Examen Periódico",
        "Examen de Reintegro",
        "Examen de Retiro"
    ]
    
    for name in names:
        connection.execute(
            sa.text("DELETE FROM tipos_examen WHERE nombre = :nombre"),
            {"nombre": name}
        )
