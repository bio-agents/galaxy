import os

from agent_shed.base.twilltestcase import common, ShedTwillTestCase

repository_name = 'freebayes_0010'
repository_description = "Galaxy's freebayes agent"
repository_long_description = "Long description of Galaxy's freebayes agent"

'''
1. Create repository freebayes_0020 and upload only the agent XML.
2. Upload the agent_data_table_conf.xml.sample file.
3. Upload sam_fa_indices.loc.sample.
4. Upload a agent_dependencies.xml file that should not parse correctly.
5. Upload a agent_dependencies.xml file that specifies a version that does not match the agent's requirements.
6. Upload a valid agent_dependencies.xml file.
7. Check for the appropriate strings on the manage repository page.
'''


class TestFreebayesRepository( ShedTwillTestCase ):
    '''Testing freebayes with agent data table entries, .loc files, and agent dependencies.'''

    def test_0000_create_or_login_admin_user( self ):
        """Create necessary user accounts and login as an admin user."""
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

    def test_0005_create_category( self ):
        """Create a category for this test suite"""
        self.create_category( name='Test 0010 Repository With Agent Dependencies', description='Tests for a repository with agent dependencies.' )

    def test_0010_create_freebayes_repository_and_upload_agent_xml( self ):
        '''Create freebayes repository and upload only freebayes.xml.'''
        '''
        We are at step 1 - Create repository freebayes_0020 and upload only the agent XML.
        Uploading only the agent XML file should result in an invalid agent and an error message on
        upload, as well as on the manage repository page.
        '''
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        category = self.test_db_util.get_category_by_name( 'Test 0010 Repository With Agent Dependencies' )
        repository = self.get_or_create_repository( name=repository_name,
                                                    description=repository_description,
                                                    long_description=repository_long_description,
                                                    owner=common.test_user_1_name,
                                                    category_id=self.security.encode_id( category.id ),
                                                    strings_displayed=[] )
        self.upload_file( repository,
                          filename='freebayes/freebayes.xml',
                          filepath=None,
                          valid_agents_only=False,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded the agent xml.',
                          strings_displayed=[ 'Metadata may have been defined', 'This file requires an entry', 'agent_data_table_conf' ],
                          strings_not_displayed=[] )
        self.display_manage_repository_page( repository, strings_displayed=[ 'Invalid agents' ], strings_not_displayed=[ 'Valid agents' ] )
        tip = self.get_repository_tip( repository )
        strings_displayed = [ 'requires an entry', 'agent_data_table_conf.xml' ]
        self.check_repository_invalid_agents_for_changeset_revision( repository, tip, strings_displayed=strings_displayed )

    def test_0015_upload_missing_agent_data_table_conf_file( self ):
        '''Upload the missing agent_data_table_conf.xml.sample file to the repository.'''
        '''
        We are at step 2 - Upload the agent_data_table_conf.xml.sample file.
        Uploading the agent_data_table_conf.xml.sample alone should not make the agent valid, but the error message should change.
        '''
        repository = self.test_db_util.get_repository_by_name_and_owner( repository_name, common.test_user_1_name )
        self.upload_file( repository,
                          filename='freebayes/agent_data_table_conf.xml.sample',
                          filepath=None,
                          valid_agents_only=False,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded the agent data table sample file.',
                          strings_displayed=[],
                          strings_not_displayed=[] )
        self.display_manage_repository_page( repository, strings_displayed=[ 'Invalid agents' ], strings_not_displayed=[ 'Valid agents' ] )
        tip = self.get_repository_tip( repository )
        strings_displayed = [ 'refers to a file', 'sam_fa_indices.loc' ]
        self.check_repository_invalid_agents_for_changeset_revision( repository, tip, strings_displayed=strings_displayed )

    def test_0020_upload_missing_sample_loc_file( self ):
        '''Upload the missing sam_fa_indices.loc.sample file to the repository.'''
        '''
        We are at step 3 - Upload the agent_data_table_conf.xml.sample file.
        Uploading the agent_data_table_conf.xml.sample alone should not make the agent valid, but the error message should change.
        '''
        repository = self.test_db_util.get_repository_by_name_and_owner( repository_name, common.test_user_1_name )
        self.upload_file( repository,
                          filename='freebayes/sam_fa_indices.loc.sample',
                          filepath=None,
                          valid_agents_only=True,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded agent data table .loc file.',
                          strings_displayed=[],
                          strings_not_displayed=[] )

    def test_0025_upload_malformed_agent_dependency_xml( self ):
        '''Upload agent_dependencies.xml with bad characters in the readme tag.'''
        '''
        We are at step 4 - Upload a agent_dependencies.xml file that should not parse correctly.
        Upload a agent_dependencies.xml file that contains <> in the text of the readme tag. This should show an error message about malformed xml.
        '''
        repository = self.test_db_util.get_repository_by_name_and_owner( repository_name, common.test_user_1_name )
        self.upload_file( repository,
                          filename=os.path.join( 'freebayes', 'malformed_agent_dependencies', 'agent_dependencies.xml' ),
                          filepath=None,
                          valid_agents_only=False,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded malformed agent dependency XML.',
                          strings_displayed=[ 'Exception attempting to parse', 'not well-formed' ],
                          strings_not_displayed=[] )

    def test_0030_upload_invalid_agent_dependency_xml( self ):
        '''Upload agent_dependencies.xml defining version 0.9.5 of the freebayes package.'''
        '''
        We are at step 5 - Upload a agent_dependencies.xml file that specifies a version that does not match the agent's requirements.
        This should result in a message about the agent dependency configuration not matching the agent's requirements.
        '''
        repository = self.test_db_util.get_repository_by_name_and_owner( repository_name, common.test_user_1_name )
        self.upload_file( repository,
                          filename=os.path.join( 'freebayes', 'invalid_agent_dependencies', 'agent_dependencies.xml' ),
                          filepath=None,
                          valid_agents_only=False,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded invalid agent dependency XML.',
                          strings_displayed=[ 'The settings for <b>name</b>, <b>version</b> and <b>type</b> from a contained agent configuration' ],
                          strings_not_displayed=[] )

    def test_0035_upload_valid_agent_dependency_xml( self ):
        '''Upload agent_dependencies.xml defining version 0.9.4_9696d0ce8a962f7bb61c4791be5ce44312b81cf8 of the freebayes package.'''
        '''
        We are at step 6 - Upload a valid agent_dependencies.xml file.
        At this stage, there should be no errors on the upload page, as every missing or invalid file has been corrected.
        '''
        repository = self.test_db_util.get_repository_by_name_and_owner( repository_name, common.test_user_1_name )
        self.upload_file( repository,
                          filename=os.path.join( 'freebayes', 'agent_dependencies.xml' ),
                          filepath=None,
                          valid_agents_only=True,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded valid agent dependency XML.',
                          strings_displayed=[],
                          strings_not_displayed=[] )

    def test_0040_verify_agent_dependencies( self ):
        '''Verify that the uploaded agent_dependencies.xml specifies the correct package versions.'''
        '''
        We are at step 7 - Check for the appropriate strings on the manage repository page.
        Verify that the manage repository page now displays the valid agent dependencies, and that there are no invalid agents shown on the manage page.
        '''
        repository = self.test_db_util.get_repository_by_name_and_owner( repository_name, common.test_user_1_name )
        strings_displayed = [ 'freebayes', '0.9.4_9696d0ce8a9', 'samagents', '0.1.18', 'Valid agents', 'package' ]
        strings_not_displayed = [ 'Invalid agents' ]
        self.display_manage_repository_page( repository, strings_displayed=strings_displayed, strings_not_displayed=strings_not_displayed )
