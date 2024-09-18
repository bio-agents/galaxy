import os
from xml.etree import ElementTree as ET


def prettify(elem):
    from xml.dom import minidom
    rough_string = ET.tostring(elem, 'utf-8')
    repaired = minidom.parseString(rough_string)
    return repaired.toprettyxml(indent='  ')


# Build a list of all agentconf xml files in the agents directory
def getfilenamelist(startdir):
    filenamelist = []
    for root, dirs, files in os.walk(startdir):
        for fn in files:
            fullfn = os.path.join(root, fn)
            if fn.endswith('agentconf.xml'):
                filenamelist.append(fullfn)
            elif fn.endswith('.xml'):
                try:
                    doc = ET.parse(fullfn)
                except:
                    print "An OOPS on", fullfn
                    raise
                rootelement = doc.getroot()
                # Only interpret those 'agent' XML files that have
                # the 'section' element.
                if rootelement.tag == 'agent':
                    if rootelement.findall('agentboxposition'):
                        filenamelist.append(fullfn)
                    else:
                        print "DBG> agent config does not have a <section>:", fullfn
    return filenamelist


class AgentBox(object):
    def __init__(self):
        from collections import defaultdict
        self.agents = defaultdict(list)
        self.sectionorders = {}

    def add(self, agentelement, agentboxpositionelement):
        section = agentboxpositionelement.attrib.get('section', '')
        label = agentboxpositionelement.attrib.get('label', '')
        order = int(agentboxpositionelement.attrib.get('order', '0'))
        sectionorder = int(agentboxpositionelement.attrib.get('sectionorder', '0'))

        # If this is the first time we encounter the section, store its order
        # number. If we have seen it before, ignore the given order and use
        # the stored one instead
        if section not in self.sectionorders:
            self.sectionorders[section] = sectionorder
        else:
            sectionorder = self.sectionorders[section]

        # Sortorder: add intelligent mix to the front
        self.agents[("%05d-%s" % (sectionorder, section), label, order, section)].append(agentelement)

    def addElementsTo(self, rootelement):
        agentkeys = self.agents.keys()
        agentkeys.sort()

        # Initialize the loop: IDs to zero, current section and label to ''
        currentsection = ''
        sectionnumber = 0
        currentlabel = ''
        labelnumber = 0
        for agentkey in agentkeys:
            section = agentkey[3]
            # If we change sections, add the new section to the XML tree,
            # and start adding stuff to the new section. If the new section
            # is '', start adding stuff to the root again.
            if currentsection != section:
                currentsection = section
                # Start the section with empty label
                currentlabel = ''
                if section:
                    sectionnumber += 1
                    attrib = {'name': section,
                              'id': "section%d" % sectionnumber}
                    sectionelement = ET.Element('section', attrib)
                    rootelement.append(sectionelement)
                    currentelement = sectionelement
                else:
                    currentelement = rootelement
            label = agentkey[1]

            # If we change labels, add the new label to the XML tree
            if currentlabel != label:
                currentlabel = label
                if label:
                    labelnumber += 1
                    attrib = {'text': label,
                              'id': "label%d" % labelnumber}
                    labelelement = ET.Element('label', attrib)
                    currentelement.append(labelelement)

            # Add the agents that are in this place
            for agentelement in self.agents[agentkey]:
                currentelement.append(agentelement)


# Analyze all the agentconf xml files given in the filenamelist
# Build a list of all sections
def scanfiles(filenamelist):
    # Build an empty agent box
    agentbox = AgentBox()

    # Read each of the files in the list
    for fn in filenamelist:
        doc = ET.parse(fn)
        root = doc.getroot()

        if root.tag == 'agent':
            agentelements = [root]
        else:
            agentelements = doc.findall('agent')

        for agentelement in agentelements:
            # Figure out where the agent XML file is, absolute path.
            if 'file' in agentelement.attrib:
                # It is mentioned, we need to make it absolute
                fileattrib = os.path.join(os.getcwd(),
                                          os.path.dirname(fn),
                                          agentelement.attrib['file'])
            else:
                # It is the current file
                fileattrib = os.path.join(os.getcwd(), fn)

            # Store the file in the attibutes of the new agent element
            attrib = {'file': fileattrib}

            # Add the tags into the attributes
            tags = agentelement.find('tags')
            if tags:
                tagarray = []
                for tag in tags.findall('tag'):
                    tagarray.append(tag.text)
                attrib['tags'] = ",".join(tagarray)
            else:
                print "DBG> No tags in", fn

            # Build the agent element
            newagentelement = ET.Element('agent', attrib)
            agentboxpositionelements = agentelement.findall('agentboxposition')
            if not agentboxpositionelements:
                print "DBG> %s has no agentboxposition" % fn
            else:
                for agentboxpositionelement in agentboxpositionelements:
                    agentbox.add(newagentelement, agentboxpositionelement)
    return agentbox


def assemble():
    filenamelist = []
    for directorytree in ['agents']:
        filenamelist.extend(getfilenamelist('agents'))
    filenamelist.sort()

    agentbox = scanfiles(filenamelist)

    agentboxelement = ET.Element('agentbox')

    agentbox.addElementsTo(agentboxelement)

    print prettify(agentboxelement)

if __name__ == "__main__":
    assemble()
