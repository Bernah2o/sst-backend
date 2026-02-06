"""add interactive lessons tables

Crea las tablas para el módulo de Lecciones Interactivas:
- interactive_lessons: Lecciones interactivas con slides
- lesson_slides: Slides individuales de cada lección
- inline_quizzes: Quizzes integrados en slides
- inline_quiz_answers: Respuestas de los quizzes inline
- interactive_activities: Actividades interactivas (drag & drop, matching, etc.)
- user_lesson_progress: Progreso del usuario en lecciones
- user_slide_progress: Progreso del usuario en slides individuales
- user_activity_attempts: Intentos del usuario en actividades

Revision ID: d7e8f90123ab
Revises: c6d7e8f90123
Create Date: 2026-02-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e8f90123ab'
down_revision = 'c6d7e8f90123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===================== INTERACTIVE LESSONS =====================
    op.create_table('interactive_lessons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('thumbnail', sa.String(length=500), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('navigation_type', sa.String(length=20), nullable=False, server_default='sequential'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('passing_score', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['module_id'], ['course_modules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interactive_lessons_id', 'interactive_lessons', ['id'], unique=False)
    op.create_index('ix_interactive_lessons_module_id', 'interactive_lessons', ['module_id'], unique=False)
    op.create_index('ix_interactive_lessons_status', 'interactive_lessons', ['status'], unique=False)

    # ===================== LESSON SLIDES =====================
    op.create_table('lesson_slides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('slide_type', sa.String(length=30), nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lesson_id'], ['interactive_lessons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lesson_slides_id', 'lesson_slides', ['id'], unique=False)
    op.create_index('ix_lesson_slides_lesson_id', 'lesson_slides', ['lesson_id'], unique=False)

    # ===================== INLINE QUIZZES =====================
    op.create_table('inline_quizzes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slide_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(length=30), nullable=False),
        sa.Column('points', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('required_to_continue', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_feedback_immediately', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['slide_id'], ['lesson_slides.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slide_id')
    )
    op.create_index('ix_inline_quizzes_id', 'inline_quizzes', ['id'], unique=False)

    # ===================== INLINE QUIZ ANSWERS =====================
    op.create_table('inline_quiz_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quiz_id', sa.Integer(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['quiz_id'], ['inline_quizzes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inline_quiz_answers_id', 'inline_quiz_answers', ['id'], unique=False)
    op.create_index('ix_inline_quiz_answers_quiz_id', 'inline_quiz_answers', ['quiz_id'], unique=False)

    # ===================== INTERACTIVE ACTIVITIES =====================
    op.create_table('interactive_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('slide_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('activity_type', sa.String(length=30), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('points', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('show_feedback', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('time_limit_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lesson_id'], ['interactive_lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slide_id'], ['lesson_slides.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interactive_activities_id', 'interactive_activities', ['id'], unique=False)
    op.create_index('ix_interactive_activities_lesson_id', 'interactive_activities', ['lesson_id'], unique=False)

    # ===================== USER LESSON PROGRESS =====================
    op.create_table('user_lesson_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('enrollment_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='not_started'),
        sa.Column('current_slide_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress_percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('quiz_score', sa.Float(), nullable=True),
        sa.Column('quiz_total_points', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('quiz_earned_points', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lesson_id'], ['interactive_lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_lesson_progress_id', 'user_lesson_progress', ['id'], unique=False)
    op.create_index('ix_user_lesson_progress_user_id', 'user_lesson_progress', ['user_id'], unique=False)
    op.create_index('ix_user_lesson_progress_lesson_id', 'user_lesson_progress', ['lesson_id'], unique=False)
    op.create_index('ix_user_lesson_progress_unique', 'user_lesson_progress', ['user_id', 'lesson_id', 'enrollment_id'], unique=True)

    # ===================== USER SLIDE PROGRESS =====================
    op.create_table('user_slide_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lesson_progress_id', sa.Integer(), nullable=False),
        sa.Column('slide_id', sa.Integer(), nullable=False),
        sa.Column('viewed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('quiz_answered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('quiz_correct', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('quiz_answer', sa.JSON(), nullable=True),
        sa.Column('points_earned', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('viewed_at', sa.DateTime(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lesson_progress_id'], ['user_lesson_progress.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slide_id'], ['lesson_slides.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_slide_progress_id', 'user_slide_progress', ['id'], unique=False)
    op.create_index('ix_user_slide_progress_unique', 'user_slide_progress', ['lesson_progress_id', 'slide_id'], unique=True)

    # ===================== USER ACTIVITY ATTEMPTS =====================
    op.create_table('user_activity_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('enrollment_id', sa.Integer(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('user_response', sa.JSON(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.JSON(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['activity_id'], ['interactive_activities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_activity_attempts_id', 'user_activity_attempts', ['id'], unique=False)
    op.create_index('ix_user_activity_attempts_user_id', 'user_activity_attempts', ['user_id'], unique=False)
    op.create_index('ix_user_activity_attempts_activity_id', 'user_activity_attempts', ['activity_id'], unique=False)


def downgrade() -> None:
    op.drop_table('user_activity_attempts')
    op.drop_table('user_slide_progress')
    op.drop_table('user_lesson_progress')
    op.drop_table('interactive_activities')
    op.drop_table('inline_quiz_answers')
    op.drop_table('inline_quizzes')
    op.drop_table('lesson_slides')
    op.drop_table('interactive_lessons')
