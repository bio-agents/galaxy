import os

from agent_shed.base.twilltestcase import common, ShedTwillTestCase

bwa_base_repository_name = 'bwa_base_repository_0100'
bwa_base_repository_description = "BWA Base"
bwa_base_repository_long_description = "BWA agent that depends on bwa 0.5.9, with a complex repository dependency pointing at package_bwa_0_5_9_0100"

bwa_package_repository_name = 'package_bwa_0_5_9_0100'
bwa_package_repository_description = "BWA Package"
bwa_package_repository_long_description = "BWA repository with a package agent dependency defined to compile and install BWA 0.5.9."

category_name = 'Test 0100 Complex Repository Dependencies'
category_description = 'Test 0100 Complex Repository Dependencies'
running_standalone = False


class TestInstallingComplexRepositoryDependencies( ShedTwillTestCase ):
    '''Test features related to installing repositories with complex repository dependencies.'''

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

    def test_0005_create_bwa_package_repository( self ):
        '''Create and populate package_bwa_0_5_9_0100.'''
        global running_standalone
        category = self.create_category( name=category_name, description=category_description )
        self.logout()
        self.login( email=common.test_user_1_email, username=common.test_user_1_name )
        repository = self.get_or_create_repository( name=bwa_package_repository_name,
                                                    description=bwa_package_repository_description,
                                                    long_description=bwa_package_repository_long_description,
                                                    owner=common.test_user_1_name,
                                                    category_id=self.security.encode_id( category.id ),
                                                    strings_displayed=[] )
        if self.repository_is_new( repository ):
            running_standalone = True
            old_agent_dependency = self.get_filename( os.path.join( 'bwa', 'complex', 'agent_dependencies.xml' ) )
            new_agent_dependency_path = self.generate_temp_path( 'test_1100', additional_paths=[ 'agent_dependency' ] )
            xml_filename = os.path.abspath( os.path.join( new_agent_dependency_path, 'agent_dependencies.xml' ) )
            file( xml_filename, 'w' ).write( file( old_agent_dependency, 'r' )
                                     .read().replace( '__PATH__', self.get_filename( 'bwa/complex' ) ) )
            self.upload_file( repository,
                              filename=xml_filename,
                              filepath=new_agent_dependency_path,
                              valid_agents_only=True,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded agent_dependencies.xml.',
                              strings_displayed=[ 'This repository currently contains a single file named <b>agent_dependencies.xml</b>' ],
                              strings_not_displayed=[] )
            self.display_manage_repository_page( repository, strings_displayed=[ 'Agent dependencies', 'consider setting its type' ] )

    def test_0010_create_bwa_base_repository( self ):
        '''Create and populate bwa_base_0100.'''
        global running_standalone
        if running_standalone:
            category = self.create_category( name=category_name, description=category_description )
            self.logout()
            self.login( email=common.test_user_1_email, username=common.test_user_1_name )
            repository = self.get_or_create_repository( name=bwa_base_repository_name,
                                                        description=bwa_base_repository_description,
                                                        long_description=bwa_base_repository_long_description,
                                                        owner=common.test_user_1_name,
                                                        category_id=self.security.encode_id( category.id ),
                                                        strings_displayed=[] )
            self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            self.upload_file( repository,
                              filename='bwa/complex/bwa_base.tar',
                              filepath=None,
                              valid_agents_only=True,
                              uncompress_file=True,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded bwa_base.tar with agent wrapper XML, but without agent dependency XML.',
                              strings_displayed=[],
                              strings_not_displayed=[] )

    def test_0015_generate_complex_repository_dependency_invalid_shed_url( self ):
        '''Generate and upload a complex repository definition that specifies an invalid agent shed URL.'''
        global running_standalone
        if running_standalone:
            dependency_path = self.generate_temp_path( 'test_0100', additional_paths=[ 'complex', 'shed' ] )
            base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
            agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            url = 'http://http://this is not an url!'
            name = agent_repository.name
            owner = agent_repository.user.username
            changeset_revision = self.get_repository_tip( agent_repository )
            strings_displayed = [ 'Repository dependencies are currently supported only within the same agent shed' ]
            repository_tuple = ( url, name, owner, changeset_revision )
            self.create_repository_dependency( repository=base_repository,
                                               filepath=dependency_path,
                                               repository_tuples=[ repository_tuple ],
                                               strings_displayed=strings_displayed,
                                               complex=True,
                                               package='bwa',
                                               version='0.5.9' )

    def test_0020_generate_complex_repository_dependency_invalid_repository_name( self ):
        '''Generate and upload a complex repository definition that specifies an invalid repository name.'''
        global running_standalone
        if running_standalone:
            dependency_path = self.generate_temp_path( 'test_0100', additional_paths=[ 'complex', 'shed' ] )
            base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
            agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            url = self.url
            name = 'invalid_repository!?'
            owner = agent_repository.user.username
            changeset_revision = self.get_repository_tip( agent_repository )
            strings_displayed = [ 'because the name is invalid.' ]
            repository_tuple = ( url, name, owner, changeset_revision )
            self.create_repository_dependency( repository=base_repository,
                                               filepath=dependency_path,
                                               repository_tuples=[ repository_tuple ],
                                               strings_displayed=strings_displayed,
                                               complex=True,
                                               package='bwa',
                                               version='0.5.9' )

    def test_0025_generate_complex_repository_dependency_invalid_owner_name( self ):
        '''Generate and upload a complex repository definition that specifies an invalid owner.'''
        global running_standalone
        if running_standalone:
            dependency_path = self.generate_temp_path( 'test_0100', additional_paths=[ 'complex', 'shed' ] )
            base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
            agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            url = self.url
            name = agent_repository.name
            owner = 'invalid_owner!?'
            changeset_revision = self.get_repository_tip( agent_repository )
            strings_displayed = [ 'because the owner is invalid.' ]
            repository_tuple = ( url, name, owner, changeset_revision )
            self.create_repository_dependency( repository=base_repository,
                                               filepath=dependency_path,
                                               repository_tuples=[ repository_tuple ],
                                               strings_displayed=strings_displayed,
                                               complex=True,
                                               package='bwa',
                                               version='0.5.9' )

    def test_0030_generate_complex_repository_dependency_invalid_changeset_revision( self ):
        '''Generate and upload a complex repository definition that specifies an invalid changeset revision.'''
        global running_standalone
        if running_standalone:
            dependency_path = self.generate_temp_path( 'test_0100', additional_paths=[ 'complex', 'shed' ] )
            base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
            agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            url = self.url
            name = agent_repository.name
            owner = agent_repository.user.username
            changeset_revision = '1234abcd'
            strings_displayed = [ 'because the changeset revision is invalid.' ]
            repository_tuple = ( url, name, owner, changeset_revision )
            self.create_repository_dependency( repository=base_repository,
                                               filepath=dependency_path,
                                               repository_tuples=[ repository_tuple ],
                                               strings_displayed=strings_displayed,
                                               complex=True,
                                               package='bwa',
                                               version='0.5.9' )

    def test_0035_generate_valid_complex_repository_dependency( self ):
        '''Generate and upload a valid agent_dependencies.xml file that specifies package_bwa_0_5_9_0100.'''
        global running_standalone
        if running_standalone:
            base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
            agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            dependency_path = self.generate_temp_path( 'test_0100', additional_paths=[ 'complex' ] )
            url = self.url
            name = agent_repository.name
            owner = agent_repository.user.username
            changeset_revision = self.get_repository_tip( agent_repository )
            repository_tuple = ( url, name, owner, changeset_revision )
            self.create_repository_dependency( repository=base_repository,
                                               filepath=dependency_path,
                                               repository_tuples=[ repository_tuple ],
                                               complex=True,
                                               package='bwa',
                                               version='0.5.9' )
            self.check_repository_dependency( base_repository, agent_repository )
            self.display_manage_repository_page( base_repository, strings_displayed=[ 'bwa', '0.5.9', 'package' ] )

    def test_0040_update_agent_repository( self ):
        '''Upload a new agent_dependencies.xml to the agent repository, and verify that the base repository displays the new changeset.'''
        global running_standalone
        if running_standalone:
            base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
            agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
            previous_changeset = self.get_repository_tip( agent_repository )
            old_agent_dependency = self.get_filename( os.path.join( 'bwa', 'complex', 'readme', 'agent_dependencies.xml' ) )
            new_agent_dependency_path = self.generate_temp_path( 'test_1100', additional_paths=[ 'agent_dependency' ] )
            xml_filename = os.path.abspath( os.path.join( new_agent_dependency_path, 'agent_dependencies.xml' ) )
            file( xml_filename, 'w' ).write( file( old_agent_dependency, 'r' )
                                     .read().replace( '__PATH__', self.get_filename( 'bwa/complex' ) ) )
            self.upload_file( agent_repository,
                              filename=xml_filename,
                              filepath=new_agent_dependency_path,
                              valid_agents_only=True,
                              uncompress_file=False,
                              remove_repo_files_not_in_tar=False,
                              commit_message='Uploaded new agent_dependencies.xml.',
                              strings_displayed=[],
                              strings_not_displayed=[] )
            # Verify that the dependency display has been updated as a result of the new agent_dependencies.xml file.
            self.display_manage_repository_page( base_repository,
                                                 strings_displayed=[ self.get_repository_tip( agent_repository ), 'bwa', '0.5.9', 'package' ],
                                                 strings_not_displayed=[ previous_changeset ] )

    def test_0045_install_base_repository( self ):
        '''Verify installation of the repository with complex repository dependencies.'''
        self.galaxy_logout()
        self.galaxy_login( email=common.admin_email, username=common.admin_username )
        base_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_base_repository_name, common.test_user_1_name )
        agent_repository = self.test_db_util.get_repository_by_name_and_owner( bwa_package_repository_name, common.test_user_1_name )
        preview_strings_displayed = [ agent_repository.name, self.get_repository_tip( agent_repository ) ]
        self.install_repository( bwa_base_repository_name,
                                 common.test_user_1_name,
                                 category_name,
                                 install_agent_dependencies=True,
                                 preview_strings_displayed=preview_strings_displayed,
                                 post_submit_strings_displayed=[ base_repository.name, agent_repository.name, 'New' ],
                                 includes_agents_for_display_in_agent_panel=True )

    def test_0050_verify_installed_repositories( self ):
        '''Verify that the installed repositories are displayed properly.'''
        base_repository = self.test_db_util.get_installed_repository_by_name_owner( bwa_base_repository_name, common.test_user_1_name )
        agent_repository = self.test_db_util.get_installed_repository_by_name_owner( bwa_package_repository_name, common.test_user_1_name )
        strings_displayed = [ 'bwa_base_repository_0100', 'user1', base_repository.installed_changeset_revision ]
        strings_displayed.extend( [ 'package_bwa_0_5_9_0100', 'user1', agent_repository.installed_changeset_revision ] )
        strings_displayed.append( self.url.replace( 'http://', '' ) )
        self.display_galaxy_browse_repositories_page( strings_displayed=strings_displayed, strings_not_displayed=[] )
        strings_displayed = [ 'package_bwa_0_5_9_0100', 'user1', agent_repository.installed_changeset_revision ]
        strings_not_displayed = [ 'Missing agent dependencies' ]
        self.display_installed_repository_manage_page( agent_repository,
                                                       strings_displayed=strings_displayed,
                                                       strings_not_displayed=strings_not_displayed )
        strings_displayed = [ 'bwa_base_repository_0100',
                              'user1',
                              'package_bwa_0_5_9_0100',
                              base_repository.installed_changeset_revision,
                              agent_repository.installed_changeset_revision ]
        strings_not_displayed = [ 'Missing agent dependencies' ]
        self.display_installed_repository_manage_page( base_repository,
                                                       strings_displayed=strings_displayed,
                                                       strings_not_displayed=strings_not_displayed )

    def test_0055_verify_complex_agent_dependency( self ):
        '''Verify that the generated env.sh contains the right data.'''
        base_repository = self.test_db_util.get_installed_repository_by_name_owner( bwa_base_repository_name, common.test_user_1_name )
        agent_repository = self.test_db_util.get_installed_repository_by_name_owner( bwa_package_repository_name, common.test_user_1_name )
        env_sh_path = self.get_env_sh_path( agent_dependency_name='bwa',
                                            agent_dependency_version='0.5.9',
                                            repository=base_repository )
        assert os.path.exists( env_sh_path ), 'env.sh was not generated in %s for this dependency.' % env_sh_path
        contents = file( env_sh_path, 'r' ).read()
        if agent_repository.installed_changeset_revision not in contents:
            raise AssertionError( 'Installed changeset revision %s not found in env.sh.\nContents of env.sh: %s' %
                                  ( agent_repository.installed_changeset_revision, contents ) )
        if 'package_bwa_0_5_9_0100' not in contents:
            raise AssertionError( 'Repository name package_bwa_0_5_9_0100 not found in env.sh.\nContents of env.sh: %s' % contents )

    def test_0060_verify_agent_dependency_uninstallation( self ):
        '''Uninstall the package_bwa_0_5_9_0100 repository.'''
        '''
        Uninstall the repository that defines a agent dependency relationship on BWA 0.5.9, and verify
        that this results in the compiled binary package also being removed.
        '''
        agent_repository = self.test_db_util.get_installed_repository_by_name_owner( bwa_package_repository_name, common.test_user_1_name )
        self.deactivate_repository( agent_repository )
        env_sh_path = os.path.join( self.galaxy_agent_dependency_dir,
                                    'bwa',
                                    '0.5.9',
                                    agent_repository.owner,
                                    agent_repository.name,
                                    agent_repository.installed_changeset_revision,
                                    'env.sh' )
        assert os.path.exists( env_sh_path ), 'Path %s does not exist after deactivating the repository that generated it.' % env_sh_path
