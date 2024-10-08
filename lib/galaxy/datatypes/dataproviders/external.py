"""
Data providers that iterate over a source that is not in memory
or not in a file.
"""

import base
import gzip
import line
import subprocess
import tempfile
import urllib
import urllib2

_TODO = """
YAGNI: ftp, image, cryptos, sockets
job queue
admin: admin server log rgx/stats, ps aux
"""

import logging
log = logging.getLogger( __name__ )


# ----------------------------------------------------------------------------- server subprocess / external prog
class SubprocessDataProvider( base.DataProvider ):
    """
    Data provider that uses the output from an intermediate program and
    subprocess as its data source.
    """
    # TODO: need better ways of checking returncode, stderr for errors and raising
    def __init__( self, *args, **kwargs ):
        """
        :param args: the list of strings used to build commands.
        :type args: variadic function args
        """
        self.exit_code = None
        command_list = args
        self.popen = self.subprocess( *command_list, **kwargs )
        # TODO:?? not communicate()?
        super( SubprocessDataProvider, self ).__init__( self.popen.stdout )
        self.exit_code = self.popen.poll()

    # NOTE: there's little protection here v. sending a ';' and a dangerous command here
    # but...we're all adults here, right? ...RIGHT?!
    def subprocess( self, *command_list, **kwargs ):
        """
        :param args: the list of strings used as commands.
        :type args: variadic function args
        """
        try:
            # how expensive is this?
            popen = subprocess.Popen( command_list, stderr=subprocess.PIPE, stdout=subprocess.PIPE )
            log.info( 'opened subrocess (%s), PID: %s' % ( str( command_list ), str( popen.pid ) ) )

        except OSError as os_err:
            command_str = ' '.join( self.command )
            raise OSError( ' '.join([ str( os_err ), ':', command_str ]) )

        return popen

    def __exit__( self, *args ):
        # poll the subrocess for an exit code
        self.exit_code = self.popen.poll()
        log.info( '%s.__exit__, exit_code: %s' % ( str( self ), str( self.exit_code ) ) )
        return super( SubprocessDataProvider, self ).__exit__( *args )

    def __str__( self ):
        # provide the pid and current return code
        source_str = ''
        if hasattr( self, 'popen' ):
            source_str = '%s:%s' % ( str( self.popen.pid ), str( self.popen.poll() ) )
        return '%s(%s)' % ( self.__class__.__name__, str( source_str ) )


class RegexSubprocessDataProvider( line.RegexLineDataProvider ):
    """
    RegexLineDataProvider that uses a SubprocessDataProvider as its data source.
    """
    # this is a conv. class and not really all that necc...
    def __init__( self, *args, **kwargs ):
        # using subprocess as proxy data source in filtered line prov.
        subproc_provider = SubprocessDataProvider( *args )
        super( RegexSubprocessDataProvider, self ).__init__( subproc_provider, **kwargs )


# ----------------------------------------------------------------------------- other apis
class URLDataProvider( base.DataProvider ):
    """
    Data provider that uses the contents of a URL for its data source.

    This can be piped through other providers (column, map, genome region, etc.).
    """
    VALID_METHODS = ( 'GET', 'POST' )

    def __init__( self, url, method='GET', data=None, **kwargs ):
        """
        :param url: the base URL to open.
        :param method: the HTTP method to use.
            Optional: defaults to 'GET'
        :param data: any data to pass (either in query for 'GET'
            or as post data with 'POST')
        :type data: dict
        """
        self.url = url
        self.method = method

        self.data = data or {}
        encoded_data = urllib.urlencode( self.data )

        if method == 'GET':
            self.url += '?%s' % ( encoded_data )
            opened = urllib2.urlopen( url )
        elif method == 'POST':
            opened = urllib2.urlopen( url, encoded_data )
        else:
            raise ValueError( 'Not a valid method: %s' % ( method ) )

        super( URLDataProvider, self ).__init__( opened, **kwargs )
        # NOTE: the request object is now accessible as self.source

    def __enter__( self ):
        pass

    def __exit__( self, *args ):
        self.source.close()


# ----------------------------------------------------------------------------- generic compression
class GzipDataProvider( base.DataProvider ):
    """
    Data provider that uses g(un)zip on a file as its source.

    This can be piped through other providers (column, map, genome region, etc.).
    """
    def __init__( self, source, **kwargs ):
        unzipped = gzip.GzipFile( source, 'rb' )
        super( GzipDataProvider, self ).__init__( unzipped, **kwargs )
        # NOTE: the GzipFile is now accessible in self.source


# ----------------------------------------------------------------------------- intermediate tempfile
class TempfileDataProvider( base.DataProvider ):
    """
    Writes the data from the given source to a temp file, allowing
    it to be used as a source where a file_name is needed (e.g. as a parameter
    to a command line agent: samagents view -t <this_provider.source.file_name>)
    """
    def __init__( self, source, **kwargs ):
        # TODO:
        raise NotImplementedError()
        # write the file here
        self.create_file
        super( TempfileDataProvider, self ).__init__( self.tmp_file, **kwargs )

    def create_file( self ):
        self.tmp_file = tempfile.NamedTemporaryFile()
        return self.tmp_file

    def write_to_file( self ):
        parent_gen = super( TempfileDataProvider, self ).__iter__()
        with open( self.tmp_file, 'w' ) as open_file:
            for datum in parent_gen:
                open_file.write( datum + '\n' )
