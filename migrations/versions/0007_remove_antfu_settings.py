"""remove obsolete provider-specific AI settings

Revision ID: 0007_remove_antfu_settings
Revises: 0006_stripe_subscription_mapping
"""

from alembic import op

revision = "0007_remove_antfu_settings"
down_revision = "0006_stripe_subscription_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key IN ('antfu_api_url', 'antfu_api_key', 'antfu_model')")


def downgrade() -> None:
    # Provider-specific settings are intentionally not restored.
    pass
