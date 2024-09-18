"""
The NCBI BLAST+ agents have been eliminated from the distribution.  The agents and
datatypes are now available in repositories named ncbi_blast_plus and
blast_datatypes, in the main Galaxy agent shed at http://agentshed.g2.bx.psu.edu.
These repositories will be installed into your local Galaxy instance at the
location discussed above by running the following command.
"""


def upgrade(migrate_engine):
    print __doc__


def downgrade(migrate_engine):
    pass
