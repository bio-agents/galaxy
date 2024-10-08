import logging
import unrestricted
import repository_suite_definition
import agent_dependency_definition
from galaxy.util.odict import odict

log = logging.getLogger( __name__ )


class Registry( object ):

    def __init__( self ):
        self.repository_types_by_label = odict()
        self.repository_types_by_label[ 'unrestricted' ] = unrestricted.Unrestricted()
        self.repository_types_by_label[ 'repository_suite_definition' ] = repository_suite_definition.RepositorySuiteDefinition()
        self.repository_types_by_label[ 'agent_dependency_definition' ] = agent_dependency_definition.AgentDependencyDefinition()

    def get_class_by_label( self, label ):
        return self.repository_types_by_label.get( label, None )
