from datetime import datetime
import hashlib
import random

from sqlalchemy import func

from galaxy import model
from galaxy import util

import logging
log = logging.getLogger( __name__ )

VALID_JOB_HASH_STRATEGIES = ["job", "user", "history", "workflow_invocation"]


class RuleHelper( object ):
    """ Utility to allow job rules to interface cleanly with the rest of
    Galaxy and shield them from low-level details of models, metrics, etc....

    Currently focus is on figuring out job statistics for a given user, but
    could interface with other stuff as well.
    """

    def __init__( self, app ):
        self.app = app

    def supports_docker( self, job_or_agent ):
        """ Job rules can pass this function a job, job_wrapper, or agent and
        determine if the underlying agent believes it can be containered.
        """
        # Not a ton of logic in this method - but the idea is to shield rule
        # developers from the details and they shouldn't have to know how to
        # interrogate agent or job to figure out if it can be run in a
        # container.
        if hasattr( job_or_agent, 'containers' ):
            agent = job_or_agent
        elif hasattr( job_or_agent, 'agent' ):
            # Have a JobWrapper-like
            agent = job_or_agent.agent
        else:
            # Have a Job object.
            agent = self.app.agentbox.get_agent( job_or_agent.agent_id )
        return any( [ c.type == "docker" for c in agent.containers ] )

    def job_count(
        self,
        **kwds
    ):
        query = self.query( model.Job )
        return self._filter_job_query( query, **kwds ).count()

    def sum_job_runtime(
        self,
        **kwds
    ):
        # TODO: Consider sum_core_hours or something that scales runtime by
        # by calculated cores per job.
        query = self.metric_query(
            select=func.sum( model.JobMetricNumeric.table.c.metric_value ),
            metric_name="runtime_seconds",
            plugin="core",
        )
        query = query.join( model.Job )
        return float( self._filter_job_query( query, **kwds ).first()[ 0 ] )

    def metric_query( self, select, metric_name, plugin, numeric=True ):
        metric_class = model.JobMetricNumeric if numeric else model.JobMetricText
        query = self.query( select )
        query = query.filter( metric_class.table.c.plugin == plugin )
        query = query.filter( metric_class.table.c.metric_name == metric_name )
        return query

    def query( self, select_expression ):
        return self.app.model.context.query( select_expression )

    def _filter_job_query(
        self,
        query,
        for_user_email=None,
        for_destination=None,
        for_destinations=None,
        for_job_states=None,
        created_in_last=None,
        updated_in_last=None,
    ):
        if for_destination is not None:
            for_destinations = [ for_destination ]

        query = query.join( model.User )
        if for_user_email is not None:
            query = query.filter( model.User.table.c.email == for_user_email )

        if for_destinations is not None:
            if len( for_destinations ) == 1:
                query = query.filter( model.Job.table.c.destination_id == for_destinations[ 0 ] )
            else:
                query = query.filter( model.Job.table.c.destination_id.in_( for_destinations ) )

        if created_in_last is not None:
            end_date = datetime.now()
            start_date = end_date - created_in_last
            query = query.filter( model.Job.table.c.create_time >= start_date )

        if updated_in_last is not None:
            end_date = datetime.now()
            start_date = end_date - updated_in_last
            log.info( end_date )
            log.info( start_date )
            query = query.filter( model.Job.table.c.update_time >= start_date )

        if for_job_states is not None:
            # Optimize the singleton case - can be much more performant in my experience.
            if len( for_job_states ) == 1:
                query = query.filter( model.Job.table.c.state == for_job_states[ 0 ] )
            else:
                query = query.filter( model.Job.table.c.state.in_( for_job_states ) )

        return query

    def should_burst( self, destination_ids, num_jobs, job_states=None ):
        """ Check if the specified destinations ``destination_ids`` have at
        least ``num_jobs`` assigned to it - send in ``job_state`` as ``queued``
        to limit this check to number of jobs queued.

        See stock_rules for an simple example of using this function - but to
        get the most out of it - it should probably be used with custom job
        rules that can respond to the bursting by allocating resources,
        launching cloud nodes, etc....
        """
        if job_states is None:
            job_states = "queued,running"
        from_destination_job_count = self.job_count(
            for_destinations=destination_ids,
            for_job_states=util.listify( job_states )
        )
        # Would this job push us over maximum job count before requiring
        # bursting (roughly... very roughly given many handler threads may be
        # scheduling jobs).
        return ( from_destination_job_count + 1 ) > int( num_jobs )

    def choose_one( self, lst, hash_value=None ):
        """ Choose a random value from supplied list. If hash_value is passed
        in then every request with that same hash_value would produce the same
        choice from the supplied list.
        """
        if hash_value is None:
            return random.choice( lst )

        if not isinstance( hash_value, int ):
            # Convert hash_value string into index
            as_hex = hashlib.md5( hash_value ).hexdigest()
            hash_value = int(as_hex, 16)
        # else assumed to be 'random' int from 0-~Inf
        random_index = hash_value % len( lst )
        return lst[ random_index ]

    def job_hash( self, job, hash_by=None ):
        """ Produce a reproducible hash for the given job on various
        criteria - for instance if hash_by is "workflow_invocation,history" -
        all jobs within the same workflow invocation will receive the same
        hash - for jobs outside of workflows all jobs within the same history
        will receive the same hash, other jobs will be hashed on job's id
        randomly.

        Primarily intended for use with ``choose_one`` above - to consistent
        route or schedule related jobs.
        """
        if hash_by is None:
            hash_by = [ "job" ]
        hash_bys = util.listify( hash_by )
        for hash_by in hash_bys:
            job_hash = self._try_hash_for_job( job, hash_by )
            if job_hash:
                return job_hash

        # Fall back to just hashing by job id, should always return a value.
        return self._try_hash_for_job( job, "job" )

    def _try_hash_for_job( self, job, hash_by ):
        """ May return False or None if hash type is invalid for that job -
        e.g. attempting to hash by user for anonymous job or by workflow
        invocation for jobs outside of workflows.
        """
        if hash_by not in VALID_JOB_HASH_STRATEGIES:
            message = "Do not know how to hash jobs by %s, must be one of %s" % ( hash_by, VALID_JOB_HASH_STRATEGIES )
            raise Exception( message )

        if hash_by == "workflow_invocation":
            return job.raw_param_dict().get( "__workflow_invocation_uuid__", None )
        elif hash_by == "history":
            return job.history_id
        elif hash_by == "user":
            user = job.user
            return user and user.id
        elif hash_by == "job":
            return job.id
