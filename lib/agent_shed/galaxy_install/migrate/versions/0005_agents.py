"""
The agents "Map with BWA for Illumina" and "Map with BWA for SOLiD" have
been eliminated from the distribution.  The agents are now available
in the repository named bwa_wrappers from the main Galaxy agent shed at
http://agentshed.g2.bx.psu.edu, and will be installed into your local
Galaxy instance at the location discussed above by running the following
command.
"""


def upgrade(migrate_engine):
    print __doc__


def downgrade(migrate_engine):
    pass
