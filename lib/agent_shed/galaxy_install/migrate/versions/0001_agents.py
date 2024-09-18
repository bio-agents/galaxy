"""
Initialize the version column of the migrate_agents database table to 1.  No agent migrations are handled in this version.
"""


def upgrade(migrate_engine):
    print __doc__


def downgrade(migrate_engine):
    pass
