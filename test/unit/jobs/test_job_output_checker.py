from unittest import TestCase
from galaxy.util.bunch import Bunch
from galaxy.jobs.output_checker import check_output
from galaxy.jobs.error_level import StdioErrorLevel
from galaxy.agents.parser.interface import AgentStdioRegex
from galaxy.model import Job


class OutputCheckerTestCase( TestCase ):

    def setUp( self ):
        self.agent = Bunch(
            stdio_regexes=[],
            stdio_exit_codes=[],
        )
        self.job = Job()
        self.job.id = "test_id"
        self.stdout = ''
        self.stderr = ''
        self.agent_exit_code = None

    def test_default_no_stderr_success( self ):
        self.__assertSuccessful()

    def test_default_stderr_failure( self ):
        self.stderr = 'foo'
        self.__assertNotSuccessful()

    def test_exit_code_error( self ):
        mock_exit_code = Bunch( range_start=1, range_end=1, error_level=StdioErrorLevel.FATAL, desc=None )
        self.agent.stdio_exit_codes.append( mock_exit_code )
        self.agent_exit_code = 1
        self.__assertNotSuccessful()

    def test_exit_code_success( self ):
        mock_exit_code = Bunch( range_start=1, range_end=1, error_level=StdioErrorLevel.FATAL, desc=None )
        self.agent.stdio_exit_codes.append( mock_exit_code )
        self.agent_exit_code = 0
        self.__assertSuccessful()

    def test_problematic_strings_matching( self ):
        problematic_str = '\x80abc'
        self.__add_regex( Bunch( match=r'.abc', stdout_match=False, stderr_match=True, error_level=StdioErrorLevel.FATAL, desc=None ) )
        self.stderr = problematic_str
        self.__assertNotSuccessful()

    def test_problematic_strings_not_matching( self ):
        problematic_str = '\x80abc'
        self.__add_regex( Bunch( match=r'.abcd', stdout_match=False, stderr_match=True, error_level=StdioErrorLevel.FATAL, desc=None ) )
        self.stderr = problematic_str
        self.__assertSuccessful()

    def test_stderr_regex_negative_match( self ):
        regex = AgentStdioRegex()
        regex.stderr_match = True
        regex.match = "foobar"
        self.__add_regex( regex )
        self.stderr = "foo"
        self.__assertSuccessful()

    def test_stderr_regex_positive_match( self ):
        regex = AgentStdioRegex()
        regex.stderr_match = True
        regex.match = "foo"
        self.__add_regex( regex )
        self.stderr = "foobar"
        self.__assertNotSuccessful()

    def test_stdout_ignored_for_stderr_regexes( self ):
        regex = AgentStdioRegex()
        regex.stderr_match = True
        regex.match = "foo"
        self.__add_regex( regex )
        self.stdout = "foobar"
        self.__assertSuccessful()

    def test_stderr_ignored_for_stdout_regexes( self ):
        regex = AgentStdioRegex()
        regex.stdout_match = True
        regex.match = "foo"
        self.__add_regex( regex )
        self.stderr = "foobar"
        self.__assertSuccessful()

    def __add_regex( self, regex ):
        self.agent.stdio_regexes.append( regex )

    def __assertSuccessful( self ):
        self.assertTrue( self.__check_output() )

    def __assertNotSuccessful( self ):
        self.assertFalse( self.__check_output() )

    def __check_output( self ):
        return check_output( self.agent, self.stdout, self.stderr, self.agent_exit_code, self.job )
