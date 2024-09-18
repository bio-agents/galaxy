#!/bin/sh

cd `dirname $0`/../..
python ./scripts/migrate_agents/migrate_agents.py 0007_agents.xml $@
