"""
Backup resolvers for when dependencies can not be loaded from the database.
Mainly suited for testing stage.

Ideally all dependencies will be stored in the database
    when a agent is added from a Agent Shed.
That should remain the preferred way of locating dependencies.

In cases where that is not possible
    for example during testing this resolver can act as a backup.
This resolver looks not just for manually added dependencies
    but also ones added from a Agent Shed.

This agent is still under development so the default behaviour could change.
It has been tested when placed in the same directory as galaxy_packages.py

At the time of writing July 3 2015 this resolver has to be plugged in.
See bottom for instructions on how to add this resolver.

"""

from os import listdir
from os.path import join, exists, getmtime

from .galaxy_packages import BaseGalaxyPackageDependencyResolver
from ..resolvers import INDETERMINATE_DEPENDENCY, Dependency

import logging
log = logging.getLogger( __name__ )

MANUAL = "manual"
PREFERRED_OWNERS = MANUAL + ",iuc,devteam"


class UnlinkedAgentShedPackageDependencyResolver(BaseGalaxyPackageDependencyResolver):
    dict_collection_visible_keys = BaseGalaxyPackageDependencyResolver.dict_collection_visible_keys + ['preferred_owners', 'select_by_owner']
    resolver_type = "unlinked_agent_shed_packages"

    def __init__(self, dependency_manager, **kwds):
        super(UnlinkedAgentShedPackageDependencyResolver, self).__init__(dependency_manager, **kwds)
        # Provide a list of preferred owners whose dependency to use
        self.preferred_owners = kwds.get('preferred_owners', PREFERRED_OWNERS).split(",")
        # Option to ignore owner and just use last modified time
        self.select_by_owner = str(kwds.get('select_by_owner', "true")).lower() != "false"

    def _find_dep_versioned( self, name, version, type='package', **kwds ):
        try:
            possibles = self._find_possible_depenencies(name, version, type)
            if len(possibles) == 0:
                log.debug("Unable to find dependency,'%s' '%s' '%s'", name, version, type)
                return INDETERMINATE_DEPENDENCY
            elif len(possibles) == 1:
                # Only one candidate found so ignore any preference rules
                return possibles[0].dependency
            else:
                # Pick the preferred one
                return self._select_preferred_dependency(possibles).dependency
        except:
            log.exception("Unexpected error hunting for dependency '%s' '%s''%s'", name, version, type)
            return INDETERMINATE_DEPENDENCY

    # Finds all possible dependency to use
    # Should be extended as required
    # Returns CandidateDepenency objects with data for preference picking
    def _find_possible_depenencies(self, name, version, type):
        possibles = []
        if exists(self.base_path):
            path = join( self.base_path, name, version )
            if exists(path):
                # First try the way without owner/name/revision
                package = self._galaxy_package_dep(path, version)
                if package != INDETERMINATE_DEPENDENCY:
                    log.debug("Found dependency '%s' '%s' '%s' at '%s'", name, version, type, path)
                    possibles.append(CandidateDepenency(package, path))
                # now try with an owner/name/revision
                for owner in listdir(path):
                    owner_path = join(path, owner)
                    for package_name in listdir(owner_path):
                        if package_name.lower().startswith("package_" + name.lower()):
                            package_path = join(owner_path, package_name)
                            for revision in listdir(package_path):
                                revision_path = join(package_path, revision)
                                package = self._galaxy_package_dep(revision_path, version)
                                if package != INDETERMINATE_DEPENDENCY:
                                    log.debug("Found dependency '%s' '%s' '%s' at '%s'", name, version, type, revision_path)
                                    possibles.append(CandidateDepenency(package, package_path, owner))
        return possibles

    def _select_preferred_dependency(self, possibles, by_owner=None):
        if by_owner is None:
            by_owner = self.select_by_owner
        preferred = []
        if by_owner:
            for owner in self.preferred_owners:
                for candidate in possibles:
                    if candidate.owner == owner:
                        preferred.append(candidate)
                    if len(preferred) == 1:
                        log.debug("Picked dependency based on owner '%s'", owner)
                        return preferred[0]
                    elif len(preferred) > 1:
                        log.debug("Multiple dependency found with owner '%s'", owner)
                        break
        if len(preferred) == 0:
            preferred = possibles
        latest_modified = 0
        for candidate in preferred:
            modified = getmtime(candidate.path)
            if latest_modified < modified:
                latest_candidate = candidate
                latest_modified = modified
        log.debug("Picking dependency at '%s' as it was the last modified", latest_candidate.path)
        return latest_candidate

    """
    #Currently no need has been found for expand the verionsless method
    #This is an example of how it could be done
    def _find_dep_default( self, name, type='package', **kwds ):
        try:
            possibles = TODO
            if len(possibles) == 0:
                log.debug("Unable to find dependency,'%s' default '%s'", name, type)
                return INDETERMINATE_DEPENDENCY
            elif len(possibles) == 1:
                #Only one candidate found so ignore any preference rules
                return possibles[0].dependency
            else:
                #Pick the preferred one
                return self._select_preferred_dependency(possibles, by_owner=False).dependency
        except:
            log.exception("Unexpected error hunting for dependency '%s' default '%s'", name, type)
            return INDETERMINATE_DEPENDENCY
    """


class CandidateDepenency(Dependency):
    dict_collection_visible_keys = Dependency.dict_collection_visible_keys + ['dependency', 'path', 'owner']
    dependency_type = 'unlinked_agent_shed_package'
    _exact = True

    @property
    def exact(self):
        return self._exact

    def __init__(self, dependency, path, owner=MANUAL):
        self.dependency = dependency
        self.path = path
        self.owner = owner

__all__ = ['UnlinkedAgentShedPackageDependencyResolver']

"""
At the time of writing July 3 2015 this resolver has to be plugged in.

Adding resolver instructions:

1. create a dependency_resolvers_config.xml file
<dependency_resolvers>
  <agent_shed_packages />
  <galaxy_packages />
  <galaxy_packages versionless="true" />
  <unlinked_agent_shed_packages />
</dependency_resolvers>


1a. ALWAYS add <agent_shed_packages /> first!!!!

1b. <galaxy_packages /> is optional as
    this resolver will also find dependency found by that resolver
1bi Current default is to use a dependency to find that way first!
1bii So an alternative version of dependency_resolvers_config.xml
<dependency_resolvers>
  <agent_shed_packages />
  <unlinked_agent_shed_packages />
  <unlinked_agent_shed_packages versionless="true" />
</dependency_resolvers>

1c. See __init__ for optional config values
1ci versionless currently is handled by the super class
    GalaxyPackageDependencyResolver

2. Add a parameter to config.ini
dependency_resolvers_config_file = ./config/dependency_resolvers_config.xml

2a. File name/path can be different
2b. config key must be dependency_resolvers_config_file

3. For planemo it may be required to specify:
--dependency_resolvers_config_file (xml file described in 1 above)
--agent_dependency_dir (root of dependencies typically galaxy/dependency_dir)
See planemo test --help for more information
"""
