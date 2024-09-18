#!/bin/sh

cd `dirname $0`/../..
python ./scripts/agent_shed/migrate_agents_to_repositories.py ./community_wsgi.ini >> ./scripts/agent_shed/migrate_agents_to_repositories.log
