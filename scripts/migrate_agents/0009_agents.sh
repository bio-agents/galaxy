#!/bin/sh

cd `dirname $0`/../..
python ./scripts/migrate_agents/migrate_agents.py 0009_agents.xml $@
