#!/bin/bash

: ${TOOL_SHED_CONFIG_FILE:=config/agent_shed.ini.sample}

stop_err() {
	echo $1
	python ./scripts/paster.py serve ${TOOL_SHED_CONFIG_FILE} --pid-file=agent_shed_bootstrap.pid --log-file=agent_shed_bootstrap.log --stop-daemon
	exit 1
}

agent_shed=`./lib/agent_shed/scripts/bootstrap_agent_shed/parse_run_sh_args.sh $@`

if [ $? -ne 0 ] ; then
	exit 0
fi

log_file="lib/agent_shed/scripts/bootstrap_agent_shed/bootstrap.log"

database_result=`python ./lib/agent_shed/scripts/bootstrap_agent_shed/bootstrap_util.py --execute check_db --config_file ${TOOL_SHED_CONFIG_FILE}`

if [ $? -ne 0 ] ; then
	stop_err "Unable to bootstrap agent shed. $database_result"
fi

echo "Bootstrapping from agent shed at $agent_shed."
echo -n "Creating database... "
python scripts/create_db.py agent_shed

if [ $? -eq 0 ] ; then
	echo "done."
else
	stop_err "failed."
fi

if [ $? -eq 0 ] ; then
	user_auth=`python ./lib/agent_shed/scripts/bootstrap_agent_shed/bootstrap_util.py --execute admin_user_info --config_file ${TOOL_SHED_CONFIG_FILE}`
	local_shed_url=`python ./lib/agent_shed/scripts/bootstrap_agent_shed/bootstrap_util.py --execute get_url --config_file ${TOOL_SHED_CONFIG_FILE}`
fi

admin_user_name=`echo $user_auth | awk 'BEGIN { FS="__SEP__" } ; { print \$1 }'`
admin_user_email=`echo $user_auth | awk 'BEGIN { FS="__SEP__" } ; { print \$2 }'`
admin_user_password=`echo $user_auth | awk 'BEGIN { FS="__SEP__" } ; { print \$3 }'`

echo -n "Creating user '$admin_user_name' with email address '$admin_user_email'..."

python lib/agent_shed/scripts/bootstrap_agent_shed/create_user_with_api_key.py ${TOOL_SHED_CONFIG_FILE} >> $log_file

echo " done."

sed -i"bak" "s/#admin_users = user1@example.org,user2@example.org/admin_users = $admin_user_email/" "${TOOL_SHED_CONFIG_FILE}"
echo -n "Starting agent shed in order to populate users and categories... "

if [ -f agent_shed_bootstrap.pid ] ; then
	stop_err "A bootstrap process is already running."
fi

python ./scripts/paster.py serve ${TOOL_SHED_CONFIG_FILE} --pid-file=agent_shed_bootstrap.pid --log-file=agent_shed_bootstrap.log --daemon > /dev/null

shed_pid=`cat agent_shed_bootstrap.pid`

while : ; do
	tail -n 1 agent_shed_bootstrap.log | grep -q "Removing PID file agent_shed_webapp.pid"
	if [ $? -eq 0 ] ; then
		echo "failed."
		echo "More information about this failure may be found in the following log snippet from agent_shed_bootstrap.log:"
		echo "========================================"
		tail -n 40 agent_shed_bootstrap.log
		echo "========================================"
		stop_err " "
	fi
	tail -n 2 agent_shed_bootstrap.log | grep -q "Starting server in PID $shed_pid"
	if [ $? -eq 0 ] ; then
		echo "done."
		break
	fi
done

echo -n "Retrieving admin user's API key from $local_shed_url..."

curl_response=`curl -s --user $admin_user_email:$admin_user_password $local_shed_url/api/authenticate/baseauth/`
# Gets an empty response only on first attempt for some reason?
sleep 1
curl_response=`curl -s --user $admin_user_email:$admin_user_password $local_shed_url/api/authenticate/baseauth/`
api_key=`echo $curl_response | grep api_key | awk -F\" '{print $4}'` 

if [[ -z $api_key && ${api_key+x} ]] ; then
		stop_err "Error getting API key for user $admin_user_email. Response: $curl_response"
fi

echo " done."

if [ $? -eq 0 ] ; then
	echo -n "Creating users... "
	python lib/agent_shed/scripts/api/create_users.py -a $api_key -f $agent_shed -t $local_shed_url >> $log_file
	echo "done."
	echo -n "Creating categories... "
	python lib/agent_shed/scripts/api/create_categories.py -a $api_key -f $agent_shed -t $local_shed_url >> $log_file
	echo "done."
else
	stop_err "Error getting API key from local agent shed."
fi

echo "Bootstrap complete, shutting down temporary agent shed process. A log has been saved to agent_shed_bootstrap.log"
python ./scripts/paster.py serve ${TOOL_SHED_CONFIG_FILE} --pid-file=agent_shed_bootstrap.pid --log-file=agent_shed_bootstrap.log --stop-daemon

exit 0
