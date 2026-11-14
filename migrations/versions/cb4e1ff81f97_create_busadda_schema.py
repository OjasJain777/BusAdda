"""Create BusAdda schema

Revision ID: cb4e1ff81f97
Revises:
Create Date: 2026-11-14 07:38:16.124777

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb4e1ff81f97'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('bus_services',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('route_number', sa.String(length=12), nullable=False),
    sa.Column('route_name', sa.String(length=150), nullable=False),
    sa.Column('region', sa.String(length=32), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=False),
    sa.Column('speed_kmph', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('route_number')
    )
    op.create_table('bus_stops',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('locality', sa.String(length=80), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('saved_routes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('source_stop_id', sa.Integer(), nullable=False),
    sa.Column('destination_stop_id', sa.Integer(), nullable=False),
    sa.Column('routing_mode', sa.Enum('shortest', 'interchanges', name='routing_mode', create_constraint=True), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['destination_stop_id'], ['bus_stops.id'], ),
    sa.ForeignKeyConstraint(['source_stop_id'], ['bus_stops.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'source_stop_id', 'destination_stop_id', 'routing_mode', name='uq_saved_journey')
    )
    with op.batch_alter_table('saved_routes', schema=None) as batch_op:
        batch_op.create_index('ix_saved_routes_destination', ['destination_stop_id'], unique=False)
        batch_op.create_index('ix_saved_routes_source', ['source_stop_id'], unique=False)
        batch_op.create_index('ix_saved_routes_user_created', ['user_id', 'created_at'], unique=False)

    op.create_table('service_stops',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('stop_id', sa.Integer(), nullable=False),
    sa.Column('stop_sequence', sa.Integer(), nullable=False),
    sa.Column('direction', sa.SmallInteger(), nullable=False),
    sa.ForeignKeyConstraint(['service_id'], ['bus_services.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stop_id'], ['bus_stops.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('service_id', 'direction', 'stop_id', name='uq_service_direction_stop'),
    sa.UniqueConstraint('service_id', 'direction', 'stop_sequence', name='uq_service_direction_sequence')
    )
    with op.batch_alter_table('service_stops', schema=None) as batch_op:
        batch_op.create_index('ix_service_stops_stop', ['stop_id'], unique=False)

    op.create_table('simulation_vehicles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('vehicle_label', sa.String(length=24), nullable=False),
    sa.Column('initial_progress', sa.Float(), nullable=False),
    sa.Column('speed_kmph', sa.Float(), nullable=False),
    sa.Column('simulation_start', sa.DateTime(), nullable=False),
    sa.Column('direction', sa.SmallInteger(), nullable=False),
    sa.ForeignKeyConstraint(['service_id'], ['bus_services.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('vehicle_label')
    )
    with op.batch_alter_table('simulation_vehicles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_simulation_vehicles_service_id'), ['service_id'], unique=False)



def downgrade():
    # Removing each table also removes its indexes, including ones backing MySQL foreign keys.
    for table in ("simulation_vehicles", "service_stops", "saved_routes", "users", "bus_stops", "bus_services"):
        op.drop_table(table)
