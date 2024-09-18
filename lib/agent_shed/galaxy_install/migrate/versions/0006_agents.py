"""
The following agents have been eliminated from the distribution:
FASTQ to BAM, SAM to FASTQ, BAM Index Statistics, Estimate Library
Complexity, Insertion size metrics for PAIRED data, SAM/BAM Hybrid
Selection Metrics, bam/sam Cleaning, Add or Replace Groups, Replace
SAM/BAM Header, Paired Read Mate Fixer, Mark Duplicate reads,
SAM/BAM Alignment Summary Metrics, SAM/BAM GC Bias Metrics, and
Reorder SAM/BAM.  The agents are now available in the repository
named picard from the main Galaxy agent shed at
http://agentshed.g2.bx.psu.edu, and will be installed into your
local Galaxy instance at the location discussed above by running
the following command.
"""


def upgrade(migrate_engine):
    print __doc__


def downgrade(migrate_engine):
    pass
