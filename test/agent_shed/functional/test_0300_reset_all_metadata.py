import os

from agent_shed.base.twilltestcase import common, ShedTwillTestCase

datatypes_repository_name = 'emboss_datatypes_0020'
datatypes_repository_description = "Galaxy applicable data formats used by Emboss agents."
datatypes_repository_long_description = "Galaxy applicable data formats used by Emboss agents.  This repository contains no agents."
emboss_repository_description = 'Galaxy wrappers for Emboss version 5.0.0 agents'
emboss_repository_long_description = 'Galaxy wrappers for Emboss version 5.0.0 agents'
workflow_filename = 'Workflow_for_0060_filter_workflow_repository.ga'
workflow_name = 'Workflow for 0060_filter_workflow_repository'

emboss_datatypes_repository_name = 'emboss_datatypes_0050'
emboss_datatypes_repository_description = "Datatypes for emboss"

emboss_repository_name = 'emboss_0050'
emboss_5_repository_name = 'emboss_5_0050'
emboss_6_repository_name = 'emboss_6_0050'

filtering_repository_name = 'filtering_0050'
filtering_repository_description = "Galaxy's filtering agent"
filtering_repository_long_description = "Long description of Galaxy's filtering agent"

freebayes_repository_name = 'freebayes_0050'
freebayes_repository_description = "Galaxy's freebayes agent"
freebayes_repository_long_description = "Long description of Galaxy's freebayes agent"

column_repository_name = 'column_maker_0050'
column_repository_description = "Add column"
column_repository_long_description = "Compute an expression on every row"

convert_repository_name = 'convert_chars_0050'
convert_repository_description = "Convert delimiters"
convert_repository_long_description = "Convert delimiters to tab"

bismark_repository_name = 'bismark_0050'
bismark_repository_description = "A flexible aligner."
bismark_repository_long_description = "A flexible aligner and methylation caller for Bisulfite-Seq applications."

category_0050_name = 'Test 0050 Circular Dependencies 5 Levels'
category_0050_description = 'Test circular dependency features'

running_standalone = False


class TestResetAllRepositoryMetadata( ShedTwillTestCase ):
    '''Verify that the "Reset selected metadata" feature works.'''

    def test_0000_initiate_users( self ):
        """Create necessary user accounts."""
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        test_user_1 = self.test_db_util.get_user( common.test_user_1_email )
        assert test_user_1 is not None, 'Problem retrieving user with email %s from the database' % common.test_user_1_email
        self.test_db_util.get_private_role( test_user_1 )
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        admin_user = self.test_db_util.get_user( common.admin_email )
        assert admin_user is not None, 'Problem retrieving user with email %s from the database' % common.admin_email
        self.test_db_util.get_private_role( admin_user )

    def test_0005_create_filtering_repository( self ):
        '''Create and populate the filtering_0000 repository.'''
        global running_standalone
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        category_0000 = self.create_category( name='Test 0000 Basic Repository Features 1', description='Test 0000 Basic Repository Features 1' )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        repository = self.get_or_create_repository( name='filtering_0000',
                                                    description="Galaxy's filtering agent",
                                                    long_description="Long description of Galaxy's filtering agent",
                                                    owner=common.test_user_1_name,
                                                    category_id=self.security.encode_id( category_0000.id ) )
        if self.repository_is_new( repository ):
            running_standalone = True
            self.upload_file( repository,
                              filename='filtering/filtering_1.1.0.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded filtering 1.1.0 tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename='filtering/filtering_2.2.0.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded filtering 2.2.0 tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0010_create_freebayes_repository( self ):
        '''Create and populate the freebayes_0010 repository.'''
        global running_standalone
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        category_0010 = self.create_category( name='Test 0010 Repository With Agent Dependencies', description='Tests for a repository with agent dependencies.' )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        repository = self.get_or_create_repository( name='freebayes_0010',
                                                    description="Galaxy's freebayes agent",
                                                    long_description="Long description of Galaxy's freebayes agent",
                                                    owner=common.test_user_1_name,
                                                    category_id=self.security.encode_id( category_0010.id ),
                                                    strings_displayed=[] )
        if running_standalone:
            self.upload_file( repository,
                              filename='freebayes/freebayes.xml',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded freebayes.xml.',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename='freebayes/agent_data_table_conf.xml.sample',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded agent_data_table_conf.xml.sample',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename='freebayes/sam_fa_indices.loc.sample',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded sam_fa_indices.loc.sample',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename='freebayes/agent_dependencies.xml',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded agent_dependencies.xml',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0015_create_datatypes_0020_repository( self ):
        '''Create and populate the emboss_datatypes_0020 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0020 = self.create_category( name='Test 0020 Basic Repository Dependencies', description='Testing basic repository dependency features.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name='emboss_datatypes_0020',
                                                        description=datatypes_repository_description,
                                                        long_description=datatypes_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category_0020.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='emboss/datatypes/datatypes_conf.xml',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded datatypes_conf.xml.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0020_create_emboss_0020_repository( self ):
        '''Create and populate the emboss_0020 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0020 = self.create_category( name='Test 0020 Basic Repository Dependencies', description='Testing basic repository dependency features.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name='emboss_0020',
                                                        description=emboss_repository_long_description,
                                                        long_description=emboss_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category_0020.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='emboss/emboss.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded emboss.tar',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0025_create_emboss_datatypes_0030_repository( self ):
        '''Create and populate the emboss_0030 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0030 = self.create_category( name='Test 0030 Repository Dependency Revisions', description='Testing repository dependencies by revision.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            datatypes_repository = self.get_or_create_repository( name='emboss_datatypes_0030',
                                                                  description=datatypes_repository_description,
                                                                  long_description=datatypes_repository_long_description,
                                                                  owner=common.test_user_1_name,
                                                                  category_id=self.security.encode_id( category_0030.id ),
                                                                  strings_displayed=[] )
            self.upload_file( datatypes_repository,
                              filename='emboss/datatypes/datatypes_conf.xml',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded datatypes_conf.xml.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0030_create_emboss_5_repository( self ):
        '''Create and populate the emboss_5_0030 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0030 = self.create_category( name='Test 0030 Repository Dependency Revisions', description='Testing repository dependencies by revision.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            emboss_5_repository = self.get_or_create_repository( name='emboss_5_0030',
                                                                 description=emboss_repository_description,
                                                                 long_description=emboss_repository_long_description,
                                                                 owner=common.test_user_1_name,
                                                                 category_id=self.security.encode_id( category_0030.id ),
                                                                 strings_displayed=[] )
            self.upload_file( emboss_5_repository,
                              filename='emboss/emboss.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded emboss.tar',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0035_create_emboss_6_repository( self ):
        '''Create and populate the emboss_6_0030 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0030 = self.create_category( name='Test 0030 Repository Dependency Revisions', description='Testing repository dependencies by revision.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            emboss_6_repository = self.get_or_create_repository( name='emboss_6_0030',
                                                                 description=emboss_repository_description,
                                                                 long_description=emboss_repository_long_description,
                                                                 owner=common.test_user_1_name,
                                                                 category_id=self.security.encode_id( category_0030.id ),
                                                                 strings_displayed=[] )
            self.upload_file( emboss_6_repository,
                              filename='emboss/emboss.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded emboss.tar',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0040_create_emboss_0030_repository( self ):
        '''Create and populate the emboss_0030 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0030 = self.create_category( name='Test 0030 Repository Dependency Revisions', description='Testing repository dependencies by revision.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            emboss_repository = self.get_or_create_repository( name='emboss_0030',
                                                               description=emboss_repository_description,
                                                               long_description=emboss_repository_long_description,
                                                               owner=common.test_user_1_name,
                                                               category_id=self.security.encode_id( category_0030.id ),
                                                               strings_displayed=[] )
            self.upload_file( emboss_repository,
                              filename='emboss/emboss.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded emboss.tar',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0045_create_repository_dependencies_for_0030( self ):
        '''Create the dependency structure for test 0030.'''
        global running_standalone
        if running_standalone:
            datatypes_repository = self.test_db_util.get_repository_by_name_and_owner( 'emboss_datatypes_0030', common.test_user_1_name )
            emboss_repository = self.test_db_util.get_repository_by_name_and_owner( 'emboss_0030', common.test_user_1_name )
            emboss_5_repository = self.test_db_util.get_repository_by_name_and_owner( 'emboss_5_0030', common.test_user_1_name )
            emboss_6_repository = self.test_db_util.get_repository_by_name_and_owner( 'emboss_6_0030', common.test_user_1_name )
            repository_dependencies_path = self.generate_temp_path( 'test_0330', additional_paths=[ 'emboss' ] )
            datatypes_tuple = ( self.url, datatypes_repository.name, datatypes_repository.user.username, self.get_repository_tip( datatypes_repository ) )
            emboss_5_tuple = ( self.url, emboss_5_repository.name, emboss_5_repository.user.username, self.get_repository_tip( emboss_5_repository ) )
            emboss_6_tuple = ( self.url, emboss_6_repository.name, emboss_6_repository.user.username, self.get_repository_tip( emboss_6_repository ) )
            self.create_repository_dependency( repository=emboss_5_repository, repository_tuples=[ datatypes_tuple ], filepath=repository_dependencies_path )
            self.create_repository_dependency( repository=emboss_6_repository, repository_tuples=[ datatypes_tuple ], filepath=repository_dependencies_path )
            self.create_repository_dependency( repository=emboss_repository, repository_tuples=[ emboss_5_tuple ], filepath=repository_dependencies_path )
            self.create_repository_dependency( repository=emboss_repository, repository_tuples=[ emboss_6_tuple ], filepath=repository_dependencies_path )

    def test_0050_create_freebayes_repository( self ):
        '''Create and populate the freebayes_0040 repository.'''
        global running_standalone
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        category_0040 = self.create_category( name='test_0040_repository_circular_dependencies', description='Testing handling of circular repository dependencies.' )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        repository = self.get_or_create_repository( name='freebayes_0040',
                                                    description="Galaxy's freebayes agent",
                                                    long_description="Long description of Galaxy's freebayes agent",
                                                    owner=common.test_user_1_name,
                                                    category_id=self.security.encode_id( category_0040.id ),
                                                    strings_displayed=[] )
        if running_standalone:
            self.upload_file( repository,
                              filename='freebayes/freebayes.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded freebayes tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0055_create_filtering_repository( self ):
        '''Create and populate the filtering_0040 repository.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category_0040 = self.create_category( name='test_0040_repository_circular_dependencies', description='Testing handling of circular repository dependencies.' )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name='filtering_0040',
                                                        description="Galaxy's filtering agent",
                                                        long_description="Long description of Galaxy's filtering agent",
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category_0040.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='filtering/filtering_1.1.0.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded filtering 1.1.0 tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0060_create_dependency_structure( self ):
        '''Create the dependency structure for test 0040.'''
        global running_standalone
        if running_standalone:
            freebayes_repository = self.test_db_util.get_repository_by_name_and_owner( 'freebayes_0040', common.test_user_1_name )
            filtering_repository = self.test_db_util.get_repository_by_name_and_owner( 'filtering_0040', common.test_user_1_name )
            repository_dependencies_path = self.generate_temp_path( 'test_0340', additional_paths=[ 'dependencies' ] )
            freebayes_tuple = ( self.url, freebayes_repository.name, freebayes_repository.user.username, self.get_repository_tip( freebayes_repository ) )
            filtering_tuple = ( self.url, filtering_repository.name, filtering_repository.user.username, self.get_repository_tip( filtering_repository ) )
            self.create_repository_dependency( repository=filtering_repository, repository_tuples=[ freebayes_tuple ], filepath=repository_dependencies_path )
            self.create_repository_dependency( repository=freebayes_repository, repository_tuples=[ filtering_tuple ], filepath=repository_dependencies_path )

    def test_0065_create_convert_repository( self ):
        '''Create and populate convert_chars_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=convert_repository_name,
                                                        description=convert_repository_description,
                                                        long_description=convert_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='convert_chars/convert_chars.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded convert_chars tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0070_create_column_repository( self ):
        '''Create and populate convert_chars_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=column_repository_name,
                                                        description=column_repository_description,
                                                        long_description=column_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='column_maker/column_maker.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded column_maker tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0075_create_emboss_datatypes_repository( self ):
        '''Create and populate emboss_datatypes_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=emboss_datatypes_repository_name,
                                                        description=datatypes_repository_description,
                                                        long_description=datatypes_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='emboss/datatypes/datatypes_conf.xml',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded datatypes_conf.xml.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0080_create_emboss_repository( self ):
        '''Create and populate emboss_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=emboss_repository_name,
                                                        description=emboss_repository_description,
                                                        long_description=emboss_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='emboss/emboss.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded emboss tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0085_create_filtering_repository( self ):
        '''Create and populate filtering_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            filtering_repository = self.get_or_create_repository( name=filtering_repository_name,
                                                                  description=filtering_repository_description,
                                                                  long_description=filtering_repository_long_description,
                                                                  owner=common.test_user_1_name,
                                                                  category_id=self.security.encode_id( category.id ),
                                                                  strings_displayed=[] )
            self.upload_file( filtering_repository,
                              filename='filtering/filtering_1.1.0.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded filtering 1.1.0 tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0090_create_freebayes_repository( self ):
        '''Create and populate freebayes_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=freebayes_repository_name,
                                                        description=freebayes_repository_description,
                                                        long_description=freebayes_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='freebayes/freebayes.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded freebayes tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0095_create_bismark_repository( self ):
        '''Create and populate bismark_0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.admin_email, username=common.admin_username )
            category = self.create_category( name=category_0050_name, description=category_0050_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=bismark_repository_name,
                                                        description=bismark_repository_description,
                                                        long_description=bismark_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.upload_file( repository,
                              filename='bismark/bismark.tar',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded bismark tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0100_create_and_upload_dependency_definitions( self ):
        '''Create the dependency structure for test 0050.'''
        global running_standalone
        if running_standalone:
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            column_repository = self.test_db_util.get_repository_by_name_and_owner( column_repository_name, common.test_user_1_name )
            convert_repository = self.test_db_util.get_repository_by_name_and_owner( convert_repository_name, common.test_user_1_name )
            datatypes_repository = self.test_db_util.get_repository_by_name_and_owner( emboss_datatypes_repository_name, common.test_user_1_name )
            emboss_repository = self.test_db_util.get_repository_by_name_and_owner( emboss_repository_name, common.test_user_1_name )
            filtering_repository = self.test_db_util.get_repository_by_name_and_owner( filtering_repository_name, common.test_user_1_name )
            freebayes_repository = self.test_db_util.get_repository_by_name_and_owner( freebayes_repository_name, common.test_user_1_name )
            bismark_repository = self.test_db_util.get_repository_by_name_and_owner( bismark_repository_name, common.test_user_1_name )
            dependency_xml_path = self.generate_temp_path( 'test_0050', additional_paths=[ 'freebayes' ] )
            # convert_chars depends on column_maker
            # column_maker depends on convert_chars
            # emboss depends on emboss_datatypes
            # emboss_datatypes depends on bismark
            # freebayes depends on freebayes, emboss, emboss_datatypes, and column_maker
            # filtering depends on emboss
            column_tuple = ( self.url, column_repository.name, column_repository.user.username, self.get_repository_tip( column_repository ) )
            convert_tuple = ( self.url, convert_repository.name, convert_repository.user.username, self.get_repository_tip( convert_repository ) )
            freebayes_tuple = ( self.url, freebayes_repository.name, freebayes_repository.user.username, self.get_repository_tip( freebayes_repository ) )
            emboss_tuple = ( self.url, emboss_repository.name, emboss_repository.user.username, self.get_repository_tip( emboss_repository ) )
            datatypes_tuple = ( self.url, datatypes_repository.name, datatypes_repository.user.username, self.get_repository_tip( datatypes_repository ) )
            bismark_tuple = ( self.url, bismark_repository.name, bismark_repository.user.username, self.get_repository_tip( bismark_repository ) )
            self.create_repository_dependency( repository=convert_repository, repository_tuples=[ column_tuple ], filepath=dependency_xml_path )
            self.create_repository_dependency( repository=column_repository, repository_tuples=[ convert_tuple ], filepath=dependency_xml_path )
            self.create_repository_dependency( repository=datatypes_repository, repository_tuples=[ bismark_tuple ], filepath=dependency_xml_path )
            self.create_repository_dependency( repository=emboss_repository, repository_tuples=[ datatypes_tuple ], filepath=dependency_xml_path )
            self.create_repository_dependency( repository=freebayes_repository,
                                               repository_tuples=[ freebayes_tuple, datatypes_tuple, emboss_tuple, column_tuple ],
                                               filepath=dependency_xml_path )
            self.create_repository_dependency( repository=filtering_repository, repository_tuples=[ emboss_tuple ], filepath=dependency_xml_path )

    def test_0105_create_filtering_repository( self ):
        '''Create and populate the filtering_0060 repository.'''
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        category_0060 = self.create_category( name='Test 0060 Workflow Features', description='Test 0060 - Workflow Features' )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        workflow_repository = self.get_or_create_repository( name='filtering_0060',
                                                             description="Galaxy's filtering agent",
                                                             long_description="Long description of Galaxy's filtering agent",
                                                             owner=common.test_user_1_name,
                                                             category_id=self.security.encode_id( category_0060.id ),
                                                             strings_displayed=[] )
        if self.repository_is_new( workflow_repository ):
            workflow = file( self.get_filename( 'filtering_workflow/Workflow_for_0060_filter_workflow_repository.ga' ), 'r' ).read()
            workflow = workflow.replace(  '__TEST_TOOL_SHED_URL__', self.url.replace( 'http://', '' ) )
            workflow_filepath = self.generate_temp_path( 'test_0360', additional_paths=[ 'filtering_workflow' ] )
            if not os.path.exists( workflow_filepath ):
                os.makedirs( workflow_filepath )
            file( os.path.join( workflow_filepath, workflow_filename ), 'w+' ).write( workflow )
            self.upload_file( workflow_repository,
                              filename=workflow_filename,
                              filepath=workflow_filepath,
                              valid_agents_only=True,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded filtering workflow.',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( workflow_repository,
                              filename='filtering/filtering_2.2.0.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded filtering 2.2.0 tarball.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0110_reset_metadata_on_all_repositories( self ):
        '''Reset metadata on all repositories, then verify that it has not changed.'''
        self.logout()
        self.login( email=common.admin_email, username=common.admin_username )
        old_metadata = dict()
        new_metadata = dict()
        repositories = self.test_db_util.get_all_repositories()
        for repository in repositories:
            old_metadata[ self.security.encode_id( repository.id ) ] = dict()
            for metadata in self.get_repository_metadata( repository ):
                old_metadata[ self.security.encode_id( repository.id ) ][ metadata.changeset_revision ] = metadata.metadata
        self.reset_metadata_on_selected_repositories( old_metadata.keys() )
        for repository in repositories:
            new_metadata[ self.security.encode_id( repository.id ) ] = dict()
            for metadata in self.get_repository_metadata( repository ):
                new_metadata[ self.security.encode_id( repository.id ) ][ metadata.changeset_revision ] = metadata.metadata
            if old_metadata[ self.security.encode_id( repository.id ) ] != new_metadata[ self.security.encode_id( repository.id ) ]:
                raise AssertionError( 'Metadata changed after reset for repository %s.' % repository.name )
