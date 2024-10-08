#!/usr/bin/env python
##Dan Blankenberg
##Script that checks agentshed tags to see if URLs are accessible.
##Does not currently handle 'download_binary'

import os
import sys
from optparse import OptionParser
import xml.etree.ElementTree as ET
import urllib2

FILENAMES = [ 'agent_dependencies.xml' ]
ACTION_TYPES = [ 'download_by_url', 'download_file' ]

def main():
    parser = OptionParser()
    parser.add_option( '-d', '--directory', dest='directory', action='store', type="string", default='.', help='Root directory' )
 
    ( options, args ) = parser.parse_args()
    
    for (dirpath, dirnames, filenames) in os.walk( options.directory ):
        for filename in filenames:
            if filename in FILENAMES:
                path = os.path.join( dirpath, filename )
                try:
                    tree = ET.parse( path )
                    root = tree.getroot()
                    for action_type in ACTION_TYPES:
                        for element in root.findall( ".//action[@type='%s']" % action_type ):
                            url = element.text.strip()
                            try:
                                urllib2.urlopen( urllib2.Request( url ) )
                            except Exception, e:
                                print "Bad URL '%s' in file '%s': %s" % ( url, path, e )
                except Exception, e:
                    print "Unable to check XML file '%s': %s" % ( path, e )

if __name__ == "__main__":
    main()
