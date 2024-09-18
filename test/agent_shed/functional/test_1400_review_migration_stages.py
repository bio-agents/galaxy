from agent_shed.base.twilltestcase import common, ShedTwillTestCase


class TestAgentMigrationStages( ShedTwillTestCase ):
    '''Verify that the migration stages display correctly.'''

    def test_0000_initiate_users( self ):
        """Create necessary user accounts and login as an admin user."""
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        admin_user = self.test_db_util.get_user( common.admin_email )
        assert admin_user is not None, 'Problem retrieving user with email %s from the database' % common.admin_email
        self.test_db_util.get_private_role( admin_user )
        self.galaxy_logout()
        self.galaxy_login( email=common.admin_email, username=common.admin_username )
        admin_user = self.test_db_util.get_user( common.admin_email )
        assert admin_user is not None, 'Problem retrieving user with email %s from the database' % common.admin_email
        self.test_db_util.get_private_role( admin_user )

    def test_0005_load_migration_stages_page( self ):
        '''Load the migration page and check for the appropriate migration stages.'''
        stages = []
        migration_message_strings = [ 'The&nbsp;Emboss&nbsp;5.0.0&nbsp;agents&nbsp;have&nbsp;been&nbsp;eliminated',
                                      'The&nbsp;freebayes&nbsp;agent&nbsp;has&nbsp;been&nbsp;eliminated',
                                      'The&nbsp;NCBI&nbsp;BLAST+&nbsp;agents',
                                      'The&nbsp;agents&nbsp;&#34;Map&nbsp;with&nbsp;BWA&nbsp;for&nbsp;Illumina&#34;',
                                      'FASTQ&nbsp;to&nbsp;BAM,&nbsp;SAM&nbsp;to&nbsp;FASTQ,&nbsp;BAM&nbsp;',
                                      'Map&nbsp;with&nbsp;Bowtie&nbsp;for&nbsp;Illumina,&nbsp;',
                                      'BAM-to-SAM&nbsp;converts&nbsp;BAM&nbsp;format' ]
        migrated_repository_names = [ 'emboss_5', 'emboss_datatypes', 'freebayes', 'ncbi_blast_plus',
                                      'blast_datatypes', 'bwa_wrappers', 'picard', 'lastz',
                                      'lastz_paired_reads', 'bowtie_color_wrappers', 'bowtie_wrappers',
                                      'xy_plot', 'bam_to_sam' ]
        migrated_agent_dependencies = [ 'emboss', '5.0.0', 'freebayes', '0.9.4_9696d0ce8a962f7bb61c4791be5ce44312b81cf8',
                                       'samagents', '0.1.18', 'blast+', '2.2.26+', 'bwa', '0.5.9', 'picard', '1.56.0',
                                       'lastz', '1.02.00', 'bowtie', '0.12.7', 'FreeBayes requires g++', 'ncurses', 'zlib',
                                       'blast.ncbi.nlm.nih.gov', 'fastx_agentkit', '0.0.13', 'samagents', '0.1.16', 'cufflinks',
                                       '2.1.1', 'R', '2.11.0' ]
        migration_scripts = [ '0002_agents.sh', '0003_agents.sh', '0004_agents.sh', '0005_agents.sh', '0006_agents.sh',
                              '0007_agents.sh', '0008_agents.sh' ]
        stages.extend( migration_scripts + migrated_agent_dependencies + migrated_repository_names )
        stages.extend( migration_message_strings )
        self.load_galaxy_agent_migrations_page( strings_displayed=stages )
