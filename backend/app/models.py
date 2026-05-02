import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index, ARRAY, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(Text, unique=True, nullable=False)
    plan = Column(Text, nullable=False, default="pilot")
    status = Column(Text, nullable=False, default="active")
    config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="tenant", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(LargeBinary, nullable=False)
    key_prefix = Column(Text, nullable=False)
    name = Column(Text)
    scopes = Column(ARRAY(Text), nullable=False, default=list)
    last_used_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    tenant = relationship("Tenant", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_tenant_active", "tenant_id", postgresql_where="revoked_at IS NULL"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(Text, nullable=False)
    title = Column(Text)
    brand = Column(Text)
    category = Column(Text)
    subcategory = Column(Text)
    price_cents = Column(Integer)
    currency = Column(String(3))
    availability = Column(Text, default="in_stock")
    popularity_score = Column(Float)
    attributes = Column(JSONB, nullable=False, default=dict)
    url = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    tenant = relationship("Tenant", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_products_tenant_external"),
        Index("ix_products_tenant_category", "tenant_id", "category"),
        Index("ix_products_attributes_gin", "attributes", postgresql_using="gin"),
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    source_url = Column(Text, nullable=False)
    s3_key = Column(Text)
    content_hash = Column(LargeBinary)
    width = Column(Integer)
    height = Column(Integer)
    status = Column(Text, nullable=False, default="pending")
    failure_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    product = relationship("Product", back_populates="images")
    embedding = relationship("Embedding", back_populates="product_image", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_product_images_tenant_status", "tenant_id", "status"),
        Index(
            "uq_product_images_hash",
            "tenant_id", "product_id", "content_hash",
            unique=True,
            postgresql_where="content_hash IS NOT NULL",
        ),
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    product_id = Column(UUID(as_uuid=True), nullable=False)
    product_image_id = Column(UUID(as_uuid=True), ForeignKey("product_images.id", ondelete="CASCADE"), nullable=False, unique=True)
    model_id = Column(Text, nullable=False)
    embedding = Column(Vector(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    product_image = relationship("ProductImage", back_populates="embedding")

    __table_args__ = (
        Index("ix_embeddings_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_embeddings_tenant_model", "tenant_id", "model_id"),
    )


class Search(Base):
    __tablename__ = "searches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    api_key_id = Column(UUID(as_uuid=True))
    query_image_hash = Column(LargeBinary)
    filters = Column(JSONB)
    result_count = Column(Integer)
    top1_score = Column(Float)
    top1_product_id = Column(UUID(as_uuid=True))
    latency_ms = Column(Integer)
    user_session_id = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_searches_tenant_created", "tenant_id", "created_at"),
    )


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    source = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="queued")
    stats = Column(JSONB)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    error = Column(Text)
