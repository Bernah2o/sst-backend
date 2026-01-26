"""normalize inmunizaciones catalogo

Revision ID: f0a1b2c3d4e5
Revises: e7f8a9b0c1d2
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


revision = "f0a1b2c3d4e5"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def _insert_inmunizacion(conn, nombre: str, descripcion: str | None) -> None:
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(
            sa.text(
                """
                INSERT INTO inmunizaciones (nombre, descripcion, activo)
                VALUES (:nombre, :descripcion, true)
                ON CONFLICT (nombre) DO NOTHING
                """
            ),
            {"nombre": nombre, "descripcion": descripcion},
        )
    elif dialect == "sqlite":
        conn.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO inmunizaciones (nombre, descripcion, activo)
                VALUES (:nombre, :descripcion, 1)
                """
            ),
            {"nombre": nombre, "descripcion": descripcion},
        )
    else:
        exists = conn.execute(
            sa.text("SELECT 1 FROM inmunizaciones WHERE nombre = :nombre LIMIT 1"),
            {"nombre": nombre},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO inmunizaciones (nombre, descripcion, activo) VALUES (:nombre, :descripcion, :activo)"
                ),
                {"nombre": nombre, "descripcion": descripcion, "activo": True},
            )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "inmunizaciones" not in tables:
        op.create_table(
            "inmunizaciones",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("nombre", sa.String(length=100), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("nombre"),
        )
        op.create_index(op.f("ix_inmunizaciones_id"), "inmunizaciones", ["id"], unique=False)
        op.create_index(op.f("ix_inmunizaciones_nombre"), "inmunizaciones", ["nombre"], unique=True)

    pi_cols = {c["name"] for c in inspector.get_columns("profesiograma_inmunizaciones")}
    needs_inmunizacion_id = "inmunizacion_id" not in pi_cols

    if needs_inmunizacion_id:
        with op.batch_alter_table("profesiograma_inmunizaciones") as batch_op:
            batch_op.add_column(sa.Column("inmunizacion_id", sa.Integer(), nullable=True))
            batch_op.create_index(
                "ix_profesiograma_inmunizaciones_inmunizacion_id",
                ["inmunizacion_id"],
                unique=False,
            )
            batch_op.create_foreign_key(
                "fk_profesiograma_inmunizaciones_inmunizacion_id_inmunizaciones",
                "inmunizaciones",
                ["inmunizacion_id"],
                ["id"],
            )

    pi_cols = {c["name"] for c in sa.inspect(conn).get_columns("profesiograma_inmunizaciones")}
    has_nombre = "nombre" in pi_cols
    has_descripcion = "descripcion" in pi_cols

    if has_nombre:
        rows = conn.execute(
            sa.text(
                "SELECT DISTINCT nombre, descripcion FROM profesiograma_inmunizaciones WHERE nombre IS NOT NULL"
            )
        ).fetchall()
        for nombre, descripcion in rows:
            _insert_inmunizacion(conn, nombre, descripcion)

        pairs = conn.execute(
            sa.text(
                "SELECT id, nombre FROM profesiograma_inmunizaciones WHERE (inmunizacion_id IS NULL) AND nombre IS NOT NULL"
            )
        ).fetchall()
        for pid, nombre in pairs:
            inm = conn.execute(
                sa.text("SELECT id FROM inmunizaciones WHERE nombre = :nombre"),
                {"nombre": nombre},
            ).fetchone()
            if inm:
                conn.execute(
                    sa.text("UPDATE profesiograma_inmunizaciones SET inmunizacion_id = :iid WHERE id = :pid"),
                    {"iid": inm[0], "pid": pid},
                )

    uniques = sa.inspect(conn).get_unique_constraints("profesiograma_inmunizaciones")
    has_uq = any(u.get("name") == "uq_profesiograma_inmunizaciones_profesiograma_inmunizacion" for u in uniques)

    with op.batch_alter_table("profesiograma_inmunizaciones") as batch_op:
        batch_op.alter_column("inmunizacion_id", existing_type=sa.Integer(), nullable=False)
        if has_nombre:
            batch_op.drop_column("nombre")
        if has_descripcion:
            batch_op.drop_column("descripcion")
        if not has_uq:
            batch_op.create_unique_constraint(
                "uq_profesiograma_inmunizaciones_profesiograma_inmunizacion",
                ["profesiograma_id", "inmunizacion_id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("profesiograma_inmunizaciones") as batch_op:
        batch_op.drop_constraint("uq_profesiograma_inmunizaciones_profesiograma_inmunizacion", type_="unique")
        batch_op.add_column(sa.Column("descripcion", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("nombre", sa.String(length=150), nullable=False))
        batch_op.drop_constraint(
            "fk_profesiograma_inmunizaciones_inmunizacion_id_inmunizaciones", type_="foreignkey"
        )
        batch_op.drop_index("ix_profesiograma_inmunizaciones_inmunizacion_id")
        batch_op.drop_column("inmunizacion_id")

    op.drop_index(op.f("ix_inmunizaciones_nombre"), table_name="inmunizaciones")
    op.drop_index(op.f("ix_inmunizaciones_id"), table_name="inmunizaciones")
    op.drop_table("inmunizaciones")
