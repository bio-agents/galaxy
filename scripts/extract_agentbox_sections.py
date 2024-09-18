import os
from collections import defaultdict
from xml.etree import ElementTree as ET

# Todo: ""
# execute from galaxy root dir

agentdict = defaultdict(list)


def main():
    doc = ET.parse("agent_conf.xml")
    root = doc.getroot()

    # index range 1-1000, current sections/agents divided between 250-750
    sectionindex = 250
    sectionfactor = int( 500 / len( root.getchildren() ) )

    for rootchild in root.getchildren():
        currentsectionlabel = ""
        if ( rootchild.tag == "section" ):
            sectionname = rootchild.attrib['name']
            # per section agent index range 1-1000, current labels/agents
            # divided between 20 and 750
            agentindex = 250
            agentfactor = int( 500 / len( rootchild.getchildren() ) )
            currentlabel = ""
            for sectionchild in rootchild.getchildren():
                if ( sectionchild.tag == "agent" ):
                    addToAgentDict(sectionchild, sectionname, sectionindex, agentindex, currentlabel)
                    agentindex += agentfactor
                elif ( sectionchild.tag == "label" ):
                    currentlabel = sectionchild.attrib["text"]
            sectionindex += sectionfactor
        elif ( rootchild.tag == "agent" ):
            addToAgentDict(rootchild, "", sectionindex, None, currentsectionlabel)
            sectionindex += sectionfactor
        elif ( rootchild.tag == "label" ):
            currentsectionlabel = rootchild.attrib["text"]
            sectionindex += sectionfactor

    # scan galaxy root agents dir for agent-specific xmls
    agentconffilelist = getfnl( os.path.join(os.getcwd(), "agents" ) )

    # foreach agent xml:
    #   check if the tags element exists in the agent xml (as child of <agent>)
    #   if not, add empty tags element for later use
    #   if this agent is in the above agentdict, add the agentboxposition element to the agent xml
    #   if not, then nothing.
    for agentconffile in agentconffilelist:
        hastags = False
        hasagentboxpos = False

        # parse agent config file into a document structure as defined by the ElementTree
        agentdoc = ET.parse(agentconffile)
        # get the root element of the agentconfig file
        agentdocroot = agentdoc.getroot()
        # check tags element, set flag
        tagselement = agentdocroot.find("tags")
        if (tagselement):
            hastags = True
        # check if agentboxposition element already exists in this tooconfig file
        agentboxposelement = agentdocroot.find("agentboxposition")
        if ( agentboxposelement ):
            hasagentboxpos = True

        if ( not ( hastags and hasagentboxpos ) ):
            original = open( agentconffile, 'r' )
            contents = original.readlines()
            original.close()

            # the new elements will be added directly below the root agent element
            addelementsatposition = 1
            # but what's on the first line? Root or not?
            if ( contents[0].startswith("<?") ):
                addelementsatposition = 2
            newelements = []
            if ( not hasagentboxpos ):
                if ( agentconffile in agentdict ):
                    for attributes in agentdict[agentconffile]:
                        # create agentboxposition element
                        sectionelement = ET.Element("agentboxposition")
                        sectionelement.attrib = attributes
                        sectionelement.tail = "\n  "
                        newelements.append( ET.tostring(sectionelement, 'utf-8') )

            if ( not hastags ):
                # create empty tags element
                newelements.append( "<tags/>\n  " )

            contents = ( contents[ 0:addelementsatposition ] + newelements +
                         contents[ addelementsatposition: ] )

            # add .new for testing/safety purposes :P
            newagentconffile = open( agentconffile, 'w' )
            newagentconffile.writelines( contents )
            newagentconffile.close()


def addToAgentDict(agent, sectionname, sectionindex, agentindex, currentlabel):
    agentfile = agent.attrib["file"]
    realagentfile = os.path.join(os.getcwd(), "agents", agentfile)

    # define attributes for the agentboxposition xml-tag
    attribdict = {}
    if ( sectionname ):
        attribdict[ "section" ] = sectionname
    if ( currentlabel ):
        attribdict[ "label" ] = currentlabel
    if ( sectionindex ):
        attribdict[ "sectionorder" ] = str(sectionindex)
    if ( agentindex ):
        attribdict[ "order" ] = str(agentindex)
    agentdict[ realagentfile ].append(attribdict)


# Build a list of all agentconf xml files in the agents directory
def getfnl(startdir):
    filenamelist = []
    for root, dirs, files in os.walk(startdir):
        for fn in files:
            fullfn = os.path.join(root, fn)
            if fn.endswith('.xml'):
                try:
                    doc = ET.parse(fullfn)
                except:
                    print "Oops, bad xml in: ", fullfn
                    raise
                rootelement = doc.getroot()
                # here we check if this xml file actually is a agent conf xml!
                if rootelement.tag == 'agent':
                    filenamelist.append(fullfn)
    return filenamelist

if __name__ == "__main__":
    main()
