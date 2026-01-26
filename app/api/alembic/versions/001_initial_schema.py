"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=512), nullable=True),
        sa.Column('role', sa.Enum('USER', 'ADMIN', 'MODERATOR', name='userrole'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Products table
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model_number', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('specifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('image_url', sa.String(length=512), nullable=True),
        sa.Column('official_url', sa.String(length=512), nullable=True),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('review_count', sa.Integer(), nullable=True),
        sa.Column('average_rating', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_products_brand', 'products', ['brand'], unique=False)
    op.create_index('ix_products_category', 'products', ['category'], unique=False)
    op.create_index('ix_products_name', 'products', ['name'], unique=False)

    # Reviewers table - updated to match Reviewer model
    op.create_table(
        'reviewers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.Enum('YOUTUBE', 'BLOG', 'PODCAST', name='platform'), nullable=False),
        sa.Column('platform_id', sa.String(length=255), nullable=False),
        sa.Column('profile_url', sa.String(length=500), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('credibility_score', sa.Float(), nullable=True, default=0.5),
        sa.Column('subscriber_count', sa.Integer(), nullable=True, default=0),
        sa.Column('total_reviews', sa.Integer(), nullable=True, default=0),
        sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reviewers_platform_id', 'reviewers', ['platform_id'], unique=True)
    op.create_index('ix_reviewers_name', 'reviewers', ['name'], unique=False)
    op.create_index('ix_reviewers_platform', 'reviewers', ['platform'], unique=False)

    # Reviews table - updated to match Review model
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('platform_url', sa.String(length=500), nullable=False),
        sa.Column('video_id', sa.String(length=100), nullable=True),
        sa.Column('review_type', sa.Enum('FULL_REVIEW', 'QUICK_LOOK', 'COMPARISON', 'LONG_TERM', 'UNBOXING', name='reviewtype'), nullable=True),
        sa.Column('overall_rating', sa.Float(), nullable=True),
        sa.Column('review_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=True, default=False),
        sa.Column('processing_status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='processingstatus'), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['reviewers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reviews_platform_url', 'reviews', ['platform_url'], unique=True)
    op.create_index('ix_reviews_product_id', 'reviews', ['product_id'], unique=False)
    op.create_index('ix_reviews_reviewer_id', 'reviews', ['reviewer_id'], unique=False)
    op.create_index('ix_reviews_product_reviewer', 'reviews', ['product_id', 'reviewer_id'], unique=False)
    op.create_index('ix_reviews_published_at', 'reviews', ['published_at'], unique=False)

    # Opinions table - updated to match Opinion model
    op.create_table(
        'opinions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('aspect', sa.String(length=100), nullable=False),
        sa.Column('sentiment', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('quote', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_opinions_aspect', 'opinions', ['aspect'], unique=False)
    op.create_index('ix_opinions_review_id', 'opinions', ['review_id'], unique=False)
    op.create_index('ix_opinions_review_aspect', 'opinions', ['review_id', 'aspect'], unique=False)
    op.create_index('ix_opinions_aspect_sentiment', 'opinions', ['aspect', 'sentiment'], unique=False)

    # Consensus table
    op.create_table(
        'consensus',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('aspect', sa.String(length=100), nullable=False),
        sa.Column('average_sentiment', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('agreement_score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('review_count', sa.Integer(), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'aspect', name='uix_consensus_product_aspect')
    )
    op.create_index('ix_consensus_product_id', 'consensus', ['product_id'], unique=False)

    # Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'ARCHIVED', 'DELETED', name='conversationstatus'), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('conversation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_user_last_message', 'conversations', ['user_id', 'last_message_at'], unique=False)

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Enum('USER', 'ASSISTANT', 'SYSTEM', name='messagerole'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intent', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('agent_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feedback_rating', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)

    # Marketplace listings table
    op.create_table(
        'marketplace_listings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_name', sa.String(length=100), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=False),
        sa.Column('seller_name', sa.String(length=255), nullable=True),
        sa.Column('seller_url', sa.String(length=512), nullable=True),
        sa.Column('seller_rating', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('listing_url', sa.String(length=512), nullable=False),
        sa.Column('price_current', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('price_original', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('shipping_info', sa.String(length=255), nullable=True),
        sa.Column('condition', sa.String(length=50), nullable=True),
        sa.Column('last_checked', sa.DateTime(timezone=True), nullable=True),
        sa.Column('listing_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_marketplace_listings_product_country', 'marketplace_listings', ['product_id', 'country_code'], unique=False)


def downgrade() -> None:
    op.drop_table('marketplace_listings')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('consensus')
    op.drop_table('opinions')
    op.drop_table('reviews')
    op.drop_table('reviewers')
    op.drop_table('products')
    op.drop_table('users')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS messagerole')
    op.execute('DROP TYPE IF EXISTS conversationstatus')
    op.execute('DROP TYPE IF EXISTS processingstatus')
    op.execute('DROP TYPE IF EXISTS reviewtype')
    op.execute('DROP TYPE IF EXISTS platform')
    op.execute('DROP TYPE IF EXISTS userrole')
