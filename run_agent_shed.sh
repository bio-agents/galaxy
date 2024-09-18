#!/bin/sh

cd `dirname $0`

./scripts/common_startup.sh

if [ -d .venv ];
then
    printf "Activating virtualenv at %s/.venv\n" $(pwd)
    . .venv/bin/activate
fi

agent_shed=`./lib/agent_shed/scripts/bootstrap_agent_shed/parse_run_sh_args.sh $@`
args=$@

if [ $? -eq 0 ] ; then
	bash ./lib/agent_shed/scripts/bootstrap_agent_shed/bootstrap_agent_shed.sh $@
	args=`echo $@ | sed "s#-\?-bootstrap_from_agent_shed $agent_shed##"`
fi

if [ -z "$TOOL_SHED_CONFIG_FILE" ]; then
    if [ -f agent_shed_wsgi.ini ]; then
        TOOL_SHED_CONFIG_FILE=agent_shed_wsgi.ini
    elif [ -f config/agent_shed.ini ]; then
        TOOL_SHED_CONFIG_FILE=config/agent_shed.ini
    else
        TOOL_SHED_CONFIG_FILE=config/agent_shed.ini.sample
    fi
    export TOOL_SHED_CONFIG_FILE
fi

python ./scripts/paster.py serve $TOOL_SHED_CONFIG_FILE --pid-file=agent_shed_webapp.pid --log-file=agent_shed_webapp.log $args
