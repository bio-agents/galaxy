#!/bin/bash

while (( $# )) ; do
    case "$1" in
	-bootstrap_from_agent_shed|--bootstrap_from_agent_shed)
		bootstrap="true"
		agent_shed=$2
		echo $agent_shed
		exit 0
		break
		;;
	esac
	shift 1
done
exit 1