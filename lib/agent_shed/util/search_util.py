import logging

from sqlalchemy import and_, false, true

log = logging.getLogger( __name__ )


def in_agent_dict( agent_dict, exact_matches_checked, agent_id=None, agent_name=None, agent_version=None ):
    found = False
    if agent_id and not agent_name and not agent_version:
        agent_dict_agent_id = agent_dict[ 'id' ].lower()
        found = ( agent_id == agent_dict_agent_id ) or \
                ( not exact_matches_checked and agent_dict_agent_id.find( agent_id ) >= 0 )
    elif agent_name and not agent_id and not agent_version:
        agent_dict_agent_name = agent_dict[ 'name' ].lower()
        found = ( agent_name == agent_dict_agent_name ) or \
                ( not exact_matches_checked and agent_dict_agent_name.find( agent_name ) >= 0 )
    elif agent_version and not agent_id and not agent_name:
        agent_dict_agent_version = agent_dict[ 'version' ].lower()
        found = ( agent_version == agent_dict_agent_version ) or \
                ( not exact_matches_checked and agent_dict_agent_version.find( agent_version ) >= 0 )
    elif agent_id and agent_name and not agent_version:
        agent_dict_agent_id = agent_dict[ 'id' ].lower()
        agent_dict_agent_name = agent_dict[ 'name' ].lower()
        found = ( agent_id == agent_dict_agent_id and agent_name == agent_dict_agent_name ) or \
                ( not exact_matches_checked and agent_dict_agent_id.find( agent_id ) >= 0 and agent_dict_agent_name.find( agent_name ) >= 0 )
    elif agent_id and agent_version and not agent_name:
        agent_dict_agent_id = agent_dict[ 'id' ].lower()
        agent_dict_agent_version = agent_dict[ 'version' ].lower()
        found = ( agent_id == agent_dict_agent_id and agent_version == agent_dict_agent_version ) or \
                ( not exact_matches_checked and agent_dict_agent_id.find( agent_id ) >= 0 and agent_dict_agent_version.find( agent_version ) >= 0 )
    elif agent_version and agent_name and not agent_id:
        agent_dict_agent_version = agent_dict[ 'version' ].lower()
        agent_dict_agent_name = agent_dict[ 'name' ].lower()
        found = ( agent_version == agent_dict_agent_version and agent_name == agent_dict_agent_name ) or \
                ( not exact_matches_checked and agent_dict_agent_version.find( agent_version ) >= 0 and agent_dict_agent_name.find( agent_name ) >= 0 )
    elif agent_version and agent_name and agent_id:
        agent_dict_agent_version = agent_dict[ 'version' ].lower()
        agent_dict_agent_name = agent_dict[ 'name' ].lower()
        agent_dict_agent_id = agent_dict[ 'id' ].lower()
        found = ( agent_version == agent_dict_agent_version and
                  agent_name == agent_dict_agent_name and
                  agent_id == agent_dict_agent_id ) or \
                ( not exact_matches_checked and
                  agent_dict_agent_version.find( agent_version ) >= 0 and
                  agent_dict_agent_name.find( agent_name ) >= 0 and
                  agent_dict_agent_id.find( agent_id ) >= 0 )
    return found


def in_workflow_dict( workflow_dict, exact_matches_checked, workflow_name ):
    workflow_dict_workflow_name = workflow_dict[ 'name' ].lower()
    return ( workflow_name == workflow_dict_workflow_name ) or \
           ( not exact_matches_checked and workflow_dict_workflow_name.find( workflow_name ) >= 0 )


def make_same_length( list1, list2 ):
    # If either list is 1 item, we'll append to it until its length is the same as the other.
    if len( list1 ) == 1:
        for i in range( 1, len( list2 ) ):
            list1.append( list1[ 0 ] )
    elif len( list2 ) == 1:
        for i in range( 1, len( list1 ) ):
            list2.append( list2[ 0 ] )
    return list1, list2


def search_ids_names( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_ids, agent_names ):
    for i, agent_id in enumerate( agent_ids ):
        agent_name = agent_names[ i ]
        if in_agent_dict( agent_dict, exact_matches_checked, agent_id=agent_id, agent_name=agent_name ):
            match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
    return match_tuples


def search_ids_versions( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_ids, agent_versions ):
    for i, agent_id in enumerate( agent_ids ):
        agent_version = agent_versions[ i ]
        if in_agent_dict( agent_dict, exact_matches_checked, agent_id=agent_id, agent_version=agent_version ):
            match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
    return match_tuples


def search_names_versions( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_names, agent_versions ):
    for i, agent_name in enumerate( agent_names ):
        agent_version = agent_versions[ i ]
        if in_agent_dict( agent_dict, exact_matches_checked, agent_name=agent_name, agent_version=agent_version ):
            match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
    return match_tuples


def search_repository_metadata( app, exact_matches_checked, agent_ids='', agent_names='', agent_versions='',
                                workflow_names='', all_workflows=False ):
    sa_session = app.model.context.current
    match_tuples = []
    ok = True
    if agent_ids or agent_names or agent_versions:
        for repository_metadata in sa_session.query( app.model.RepositoryMetadata ) \
                                             .filter( app.model.RepositoryMetadata.table.c.includes_agents == true() ) \
                                             .join( app.model.Repository ) \
                                             .filter( and_( app.model.Repository.table.c.deleted == false(),
                                                            app.model.Repository.table.c.deprecated == false() ) ):
            metadata = repository_metadata.metadata
            if metadata:
                agents = metadata.get( 'agents', [] )
                for agent_dict in agents:
                    if agent_ids and not agent_names and not agent_versions:
                        for agent_id in agent_ids:
                            if in_agent_dict( agent_dict, exact_matches_checked, agent_id=agent_id ):
                                match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
                    elif agent_names and not agent_ids and not agent_versions:
                        for agent_name in agent_names:
                            if in_agent_dict( agent_dict, exact_matches_checked, agent_name=agent_name ):
                                match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
                    elif agent_versions and not agent_ids and not agent_names:
                        for agent_version in agent_versions:
                            if in_agent_dict( agent_dict, exact_matches_checked, agent_version=agent_version ):
                                match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
                    elif agent_ids and agent_names and not agent_versions:
                        if len( agent_ids ) == len( agent_names ):
                            match_tuples = search_ids_names( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_ids, agent_names )
                        elif len( agent_ids ) == 1 or len( agent_names ) == 1:
                            agent_ids, agent_names = make_same_length( agent_ids, agent_names )
                            match_tuples = search_ids_names( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_ids, agent_names )
                        else:
                            ok = False
                    elif agent_ids and agent_versions and not agent_names:
                        if len( agent_ids ) == len( agent_versions ):
                            match_tuples = search_ids_versions( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_ids, agent_versions )
                        elif len( agent_ids ) == 1 or len( agent_versions ) == 1:
                            agent_ids, agent_versions = make_same_length( agent_ids, agent_versions )
                            match_tuples = search_ids_versions( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_ids, agent_versions )
                        else:
                            ok = False
                    elif agent_versions and agent_names and not agent_ids:
                        if len( agent_versions ) == len( agent_names ):
                            match_tuples = search_names_versions( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_names, agent_versions )
                        elif len( agent_versions ) == 1 or len( agent_names ) == 1:
                            agent_versions, agent_names = make_same_length( agent_versions, agent_names )
                            match_tuples = search_names_versions( agent_dict, exact_matches_checked, match_tuples, repository_metadata, agent_names, agent_versions )
                        else:
                            ok = False
                    elif agent_versions and agent_names and agent_ids:
                        if len( agent_versions ) == len( agent_names ) and len( agent_names ) == len( agent_ids ):
                            for i, agent_version in enumerate( agent_versions ):
                                agent_name = agent_names[ i ]
                                agent_id = agent_ids[ i ]
                                if in_agent_dict( agent_dict, exact_matches_checked, agent_id=agent_id, agent_name=agent_name, agent_version=agent_version ):
                                    match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
                        else:
                            ok = False
    elif workflow_names or all_workflows:
        for repository_metadata in sa_session.query( app.model.RepositoryMetadata ) \
                                             .filter( app.model.RepositoryMetadata.table.c.includes_workflows == true() ) \
                                             .join( app.model.Repository ) \
                                             .filter( and_( app.model.Repository.table.c.deleted == false(),
                                                            app.model.Repository.table.c.deprecated == false() ) ):
            metadata = repository_metadata.metadata
            if metadata:
                # metadata[ 'workflows' ] is a list of tuples where each contained tuple is
                # [ <relative path to the .ga file in the repository>, <exported workflow dict> ]
                if workflow_names:
                    workflow_tups = metadata.get( 'workflows', [] )
                    workflows = [ workflow_tup[1] for workflow_tup in workflow_tups ]
                    for workflow_dict in workflows:
                        for workflow_name in workflow_names:
                            if in_workflow_dict( workflow_dict, exact_matches_checked, workflow_name ):
                                match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
                elif all_workflows:
                    match_tuples.append( ( repository_metadata.repository_id, repository_metadata.changeset_revision ) )
    return ok, match_tuples
