import os

from agent_shed.base.twilltestcase import common, ShedTwillTestCase


class UninstallingAndReinstallingRepositories( ShedTwillTestCase ):
    '''Test uninstalling and reinstalling a repository with agent dependencies.'''

    def test_0000_initiate_users( self ):
        """Create necessary user accounts."""
        self.galaxy_logout()
        self.galaxy_login( email=common.admin_email, username=common.admin_username )
        admin_user = self.test_db_util.get_galaxy_user( common.admin_email )
        assert admin_user is not None, 'Problem retrieving user with email %s from the database' % common.admin_email
        self.test_db_util.get_galaxy_private_role( admin_user )
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

    def test_0005_ensure_repositories_and_categories_exist( self ):
        '''Create the 0010 category and upload the freebayes repository to the agent shed, if necessary.'''
        category = self.create_category( name='Test 0010 Repository With Agent Dependencies', description='Tests for a repository with agent dependencies.' )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        repository = self.get_or_create_repository( name='freebayes_0010',
                                                    description="Galaxy's freebayes agent",
                                                    long_description="Long description of Galaxy's freebayes agent",
                                                    owner=common.test_user_1_name,
                                                    category_id=self.security.encode_id( category.id ) )
        if self.repository_is_new( repository ):
            self.upload_file( repository,
                              filename='freebayes/freebayes.xml',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded the agent xml.',
                              strings_displayed=[ 'Metadata may have been defined', 'This file requires an entry', 'agent_data_table_conf' ],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename='freebayes/agent_data_table_conf.xml.sample',
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded the agent data table sample file.',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename='freebayes/sam_fa_indices.loc.sample',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded agent data table .loc file.',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename=os.path.join( 'freebayes', 'malformed_agent_dependencies', 'agent_dependencies.xml' ),
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded malformed agent dependency XML.',
                              strings_displayed=[ 'Exception attempting to parse', 'not well-formed' ],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename=os.path.join( 'freebayes', 'invalid_agent_dependencies', 'agent_dependencies.xml' ),
                              filepath=None,
                              valid_agents_only=False,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded invalid agent dependency XML.',
                              strings_displayed=[ 'The settings for <b>name</b>, <b>version</b> and <b>type</b> from a contained agent configuration' ],
                              strings_not_displayed=[] )
            self.upload_file( repository,
                              filename=os.path.join( 'freebayes', 'agent_dependencies.xml' ),
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded valid agent dependency XML.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0010_install_freebayes_repository( self ):
        '''Install the freebayes repository into the Galaxy instance.'''
        self.galaxy_logout()
        self.galaxy_login( email=common.admin_email, username=common.admin_username )
        strings_displayed = [ 'Handle', 'agent dependencies', 'freebayes', '0.9.4_9696d0ce8a9', 'samagents', '0.1.18' ]
        self.install_repository( 'freebayes_0010',
                                 common.test_user_1_name,
                                 'Test 0010 Repository With Agent Dependencies',
                                 strings_displayed=strings_displayed,
                                 new_agent_panel_section_label='test_1210' )
        installed_repository = self.test_db_util.get_installed_repository_by_name_owner( 'freebayes_0010', common.test_user_1_name )
        strings_displayed = [ 'freebayes_0010',
                              "Galaxy's freebayes agent",
                              'user1',
                              self.url.replace( 'http://', '' ),
                              installed_repository.installed_changeset_revision ]
        self.display_galaxy_browse_repositories_page( strings_displayed=strings_displayed )

    def test_0015_uninstall_freebayes_repository( self ):
        '''Uninstall the freebayes repository.'''
        installed_repository = self.test_db_util.get_installed_repository_by_name_owner( 'freebayes_0010', common.test_user_1_name )
        self.uninstall_repository( installed_repository )
        strings_not_displayed = [ installed_repository.name, installed_repository.installed_changeset_revision ]
        self.display_galaxy_browse_repositories_page( strings_not_displayed=strings_not_displayed )

    def test_0020_reinstall_freebayes_repository( self ):
        '''Reinstall the freebayes repository.'''
        installed_repository = self.test_db_util.get_installed_repository_by_name_owner( 'freebayes_0010', common.test_user_1_name )
        self.reinstall_repository( installed_repository )
        strings_displayed = [ 'freebayes_0010',
                              "Galaxy's freebayes agent",
                              'user1',
                              self.url.replace( 'http://', '' ),
                              installed_repository.installed_changeset_revision ]
        self.display_galaxy_browse_repositories_page( strings_displayed=strings_displayed )
        strings_displayed.extend( [ 'Installed agent shed repository', 'Valid agents', 'FreeBayes' ] )
        self.display_installed_repository_manage_page( installed_repository, strings_displayed=strings_displayed )
        self.verify_agent_metadata_for_installed_repository( installed_repository )

    def test_0025_deactivate_freebayes_repository( self ):
        '''Deactivate the freebayes repository without removing it from disk.'''
        installed_repository = self.test_db_util.get_installed_repository_by_name_owner( 'freebayes_0010', common.test_user_1_name )
        self.deactivate_repository( installed_repository )
        strings_not_displayed = [ installed_repository.name, installed_repository.installed_changeset_revision ]
        self.display_galaxy_browse_repositories_page( strings_not_displayed=strings_not_displayed )

    def test_0030_reactivate_freebayes_repository( self ):
        '''Reactivate the freebayes repository and verify that it now shows up in the list of installed repositories.'''
        installed_repository = self.test_db_util.get_installed_repository_by_name_owner( 'freebayes_0010', common.test_user_1_name )
        self.reactivate_repository( installed_repository )
        strings_displayed = [ 'freebayes_0010',
                              "Galaxy's freebayes agent",
                              'user1',
                              self.url.replace( 'http://', '' ),
                              installed_repository.installed_changeset_revision ]
        self.display_galaxy_browse_repositories_page( strings_displayed=strings_displayed )
        strings_displayed.extend( [ 'Installed agent shed repository', 'Valid agents', 'FreeBayes' ] )
        self.display_installed_repository_manage_page( installed_repository, strings_displayed=strings_displayed )
        self.verify_agent_metadata_for_installed_repository( installed_repository )
