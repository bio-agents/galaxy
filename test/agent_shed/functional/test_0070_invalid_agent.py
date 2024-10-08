from agent_shed.base.twilltestcase import common, ShedTwillTestCase

repository_name = 'bismark_0070'
repository_description = "Galaxy's bismark wrapper"
repository_long_description = "Long description of Galaxy's bismark wrapper"
category_name = 'Test 0070 Invalid Agent Revisions'
category_description = 'Tests for a repository with invalid agent revisions.'


class TestBismarkRepository( ShedTwillTestCase ):
    '''Testing bismark with valid and invalid agent entries.'''

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

    def test_0005_create_category_and_repository( self ):
        """Create a category for this test suite, then create and populate a bismark repository. It should contain at least one each valid and invalid agent."""
        category = self.create_category( name=category_name, description=category_description )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        repository = self.get_or_create_repository( name=repository_name,
                                                    description=repository_description,
                                                    long_description=repository_long_description,
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
        self.display_manage_repository_page( repository, strings_displayed=[ 'Invalid agents' ] )
        invalid_revision = self.get_repository_tip( repository )
        self.upload_file( repository,
                          filename='bismark/bismark_methylation_extractor.xml',
                          filepath=None,
                          valid_agents_only=False,
                          uncompress_file=False,
                          remove_repo_files_not_in_tar=False,
                          commit_message='Uploaded an updated agent xml.',
                          strings_displayed=[],
                          strings_not_displayed=[] )
        valid_revision = self.get_repository_tip( repository )
        self.test_db_util.refresh( repository )
        agent_guid = '%s/repos/user1/bismark_0070/bismark_methylation_extractor/0.7.7.3' % self.url.replace( 'http://', '' ).rstrip( '/' )
        agent_metadata_strings_displayed = [ agent_guid,
                                            '0.7.7.3',  # The agent version.
                                            'bismark_methylation_extractor',  # The agent ID.
                                            'Bismark',  # The agent name.
                                            'methylation extractor' ]  # The agent description.
        agent_page_strings_displayed = [ 'Bismark (version 0.7.7.3)' ]
        self.check_repository_agents_for_changeset_revision( repository,
                                                            valid_revision,
                                                            agent_metadata_strings_displayed=agent_metadata_strings_displayed,
                                                            agent_page_strings_displayed=agent_page_strings_displayed )
        self.check_repository_invalid_agents_for_changeset_revision( repository, invalid_revision )
