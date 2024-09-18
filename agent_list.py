import os
import sys

# read agent_conf.xml to get all the agent xml file names
onoff = 1
agent_list = []
agent_conf_file = os.environ.get( 'GALAXY_TEST_TOOL_CONF', None )

if agent_conf_file is None:
    for possible_agent_file in [ 'config/agent_conf.xml', 'agent_conf.xml', 'config/agent_conf.xml.sample' ]:
        agent_conf_file = possible_agent_file
        if os.path.isfile( possible_agent_file ):
            break

if agent_conf_file is None or not os.path.isfile(agent_conf_file):
    sys.stderr.write( "Agent config file not found: {}\n".format(agent_conf_file) )
    sys.exit(1)

for line in open(agent_conf_file, "r"):
    if line.find("<!--") != -1:
        onoff = 0
    if line.find("file") != -1 and onoff == 1:
        strs = line.split('\"')
        agent_list.append(strs[1])
    if line.find("<section") != -1 and onoff == 1:
        keys = line.strip().split('\"')
        n = 0
        strtmp = "section::"
        while n < len(keys):
            if keys[n].find("id") != -1:
                strtmp = strtmp + keys[n + 1]
            if keys[n].find("name") != -1:
                strtmp = strtmp + keys[n + 1] + "-"
            n = n + 1
        agent_list.append(strtmp.replace(' ', '_'))
    if line.find("-->") != -1:
        onoff = 1

# read agent info from every agent xml file
name = []
id = []
desc = []
agent_infos = []
for agent in agent_list:
    if agent.find("section") != -1:
        agent_info = dict()
        agent_info["id"] = agent
        agent_infos.append(agent_info)
    if os.path.exists("agents/" + agent):
        for line in open("agents/" + agent):
            if line.find("<agent ") != -1 and line.find("id") != -1:
                keys = line.strip().split('\"')
                agent_info = dict()
                agent_info["desc"] = ''
                for n in range(len(keys) - 1):
                    if " id=" in keys[n]:
                        agent_info["id"] = keys[n + 1].replace(' ', '_')
                    if " name=" in keys[n]:
                        agent_info["name"] = keys[n + 1]
                    if " description=" in keys[n]:
                        agent_info["desc"] = keys[n + 1]
                agent_infos.append(agent_info)
                break

flag = 0
if len(sys.argv) == 1:
    for agent_info in agent_infos:
        if agent_info["id"].find("section") != -1:
            print "==========================================================================================================================================="
            print "%-45s\t%-40s\t%s" % ("id", "name", agent_info["id"])
            print "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -"
        else:
            print "%-45s\t%-40s" % (agent_info["id"], agent_info["name"])
else:
    for agent_info in agent_infos:
        if agent_info["id"].find("section") != -1:
            flag = 0
        elif flag == 1:
            print " functional.test_agentbox:TestForAgent_%s" % agent_info["id"],
        if agent_info["id"].replace('section::', '') == sys.argv[1]:
            flag = 1
