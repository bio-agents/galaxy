from galaxy.util.bunch import Bunch

from galaxy.agents.agentbox.filters import FilterFactory


def test_stock_filtering_requires_login_agents( ):
    anonymous_user_trans = mock_trans( has_user=False )
    filters = filter_factory( {} ).build_filters( mock_trans() )[ 'agent' ]
    assert not is_filtered( filters, anonymous_user_trans, mock_agent( require_login=False ) )
    assert is_filtered( filters, anonymous_user_trans, mock_agent( require_login=True ) )

    logged_in_trans = mock_trans( has_user=True )
    filters = filter_factory( {} ).build_filters( logged_in_trans )[ 'agent' ]
    assert not is_filtered( filters, logged_in_trans, mock_agent( require_login=True ) )


def test_stock_filtering_hidden_agents( ):
    filters = filter_factory( {} ).build_filters( mock_trans() )[ 'agent' ]
    assert not is_filtered( filters, mock_trans(), mock_agent( hidden=False ) )
    assert is_filtered( filters, mock_trans(), mock_agent( hidden=True ) )


def test_trackster_filtering( ):
    filters = filter_factory( {} ).build_filters( mock_trans(), trackster=True )[ 'agent' ]
    # Ekkk... is trackster_conf broken? Why is it showing up.
    # assert is_filtered( filters, mock_trans(), mock_agent( trackster_conf=False ) )
    assert not is_filtered( filters, mock_trans(), mock_agent( trackster_conf=True ) )


def test_custom_filters():
    filters = filter_factory().build_filters( mock_trans() )
    agent_filters = filters[ "agent" ]
    # TODO: the fact that -1 is the custom filter is an implementation
    # detail that should not be tested here.
    assert agent_filters[ -1 ].__doc__ == "Test Filter Agent"

    section_filters = filters[ "section" ]
    assert section_filters[ 0 ].__doc__ == "Test Filter Section"

    label_filters = filters[ "label" ]
    assert label_filters[ 0 ].__doc__ == "Test Filter Label 1"
    assert label_filters[ 1 ].__doc__ == "Test Filter Label 2"


def filter_factory(config_dict=None):
    if config_dict is None:
        config_dict = dict(
            agent_filters=["filtermod:filter_agent"],
            agent_section_filters=["filtermod:filter_section"],
            agent_label_filters=["filtermod:filter_label_1", "filtermod:filter_label_2"],
        )
    config = Bunch( **config_dict )
    config.agentbox_filter_base_modules = "galaxy.agents.filters,agents.filter_modules"
    app = Bunch(config=config)
    agentbox = Bunch(app=app)
    return FilterFactory(agentbox)


def is_filtered( filters, trans, agent ):
    context = Bunch( trans=trans )
    return not all( map( lambda filter: filter( context, agent ), filters ) )


def mock_agent( require_login=False, hidden=False, trackster_conf=False, allow_access=True ):
    def allow_user_access(user, attempting_access):
        assert not attempting_access
        return allow_access

    agent = Bunch(
        require_login=require_login,
        hidden=hidden,
        trackster_conf=trackster_conf,
        allow_user_access=allow_user_access,
    )
    return agent


def mock_trans( has_user=True, is_admin=False ):
    trans = Bunch( user_is_admin=lambda: is_admin )
    if has_user:
        trans.user = Bunch(preferences={})
    else:
        trans.user = None
    return trans
