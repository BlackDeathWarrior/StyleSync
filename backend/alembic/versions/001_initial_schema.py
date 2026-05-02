"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'tenants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('slug', sa.Text, unique=True, nullable=False),
        sa.Column('plan', sa.Text, nullable=False, server_default='pilot'),
        sa.Column('status', sa.Text, nullable=False, server_default='active'),
        sa.Column('config', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'api_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.LargeBinary, nullable=False),
        sa.Column('key_prefix', sa.Text, nullable=False),
        sa.Column('name', sa.Text),
        sa.Column('scopes', ARRAY(sa.Text), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_api_keys_tenant_active', 'api_keys', ['tenant_id'],
                    postgresql_where=sa.text('revoked_at IS NULL'))

    op.create_table(
        'products',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.Text, nullable=False),
        sa.Column('title', sa.Text),
        sa.Column('brand', sa.Text),
        sa.Column('category', sa.Text),
        sa.Column('subcategory', sa.Text),
        sa.Column('price_cents', sa.Integer),
        sa.Column('currency', sa.String(3)),
        sa.Column('availability', sa.Text, server_default='in_stock'),
        sa.Column('popularity_score', sa.Float),
        sa.Column('attributes', JSONB, nullable=False, server_default='{}'),
        sa.Column('url', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'external_id', name='uq_products_tenant_external'),
    )
    op.create_index('ix_products_tenant_category', 'products', ['tenant_id', 'category'])
    op.create_index('ix_products_attributes_gin', 'products', ['attributes'], postgresql_using='gin')

    op.create_table(
        'product_images',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_url', sa.Text, nullable=False),
        sa.Column('s3_key', sa.Text),
        sa.Column('content_hash', sa.LargeBinary),
        sa.Column('width', sa.Integer),
        sa.Column('height', sa.Integer),
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('failure_reason', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_product_images_tenant_status', 'product_images', ['tenant_id', 'status'])
    op.create_index('uq_product_images_hash', 'product_images', ['tenant_id', 'product_id', 'content_hash'],
                    unique=True, postgresql_where=sa.text('content_hash IS NOT NULL'))

    op.create_table(
        'embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', UUID(as_uuid=True), nullable=False),
        sa.Column('product_image_id', UUID(as_uuid=True), sa.ForeignKey('product_images.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('model_id', sa.Text, nullable=False),
        sa.Column('embedding', Vector(512), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_embeddings_hnsw', 'embeddings', ['embedding'],
                    postgresql_using='hnsw',
                    postgresql_with={'m': 16, 'ef_construction': 64},
                    postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_embeddings_tenant_model', 'embeddings', ['tenant_id', 'model_id'])

    op.create_table(
        'searches',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('api_key_id', UUID(as_uuid=True)),
        sa.Column('query_image_hash', sa.LargeBinary),
        sa.Column('filters', JSONB),
        sa.Column('result_count', sa.Integer),
        sa.Column('top1_score', sa.Float),
        sa.Column('top1_product_id', UUID(as_uuid=True)),
        sa.Column('latency_ms', sa.Integer),
        sa.Column('user_session_id', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_searches_tenant_created', 'searches', ['tenant_id', 'created_at'])

    op.create_table(
        'sync_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.Text, nullable=False),
        sa.Column('status', sa.Text, nullable=False, server_default='queued'),
        sa.Column('stats', JSONB),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('error', sa.Text),
    )

    op.execute("""
        INSERT INTO tenants (id, name, slug, plan, status, config)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Pilot Tenant', 'pilot', 'pilot', 'active', '{}')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('sync_jobs')
    op.drop_table('searches')
    op.drop_table('embeddings')
    op.drop_table('product_images')
    op.drop_table('products')
    op.drop_table('api_keys')
    op.drop_table('tenants')
    op.execute("DROP EXTENSION IF EXISTS vector")
