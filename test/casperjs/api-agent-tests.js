var require = patchRequire( require ),
    spaceghost = require( 'spaceghost' ).fromCasper( casper ),
    xpath = require( 'casper' ).selectXPath,
    utils = require( 'utils' ),
    format = utils.format;

spaceghost.test.begin( 'Test the agents API', 0, function suite( test ){
    spaceghost.start();

// =================================================================== SET UP
var email = spaceghost.user.getRandomEmail(),
    password = '123456';
if( spaceghost.fixtureData.testUser ){
    email = spaceghost.fixtureData.testUser.email;
    password = spaceghost.fixtureData.testUser.password;
}
spaceghost.user.loginOrRegisterUser( email, password );

function compareObjs( obj1, where ){
    for( var key in where ){
        if( where.hasOwnProperty( key ) ){
            if( !obj1.hasOwnProperty( key )  ){ return false; }
            if( obj1[ key ] !== where[ key ] ){ return false; }
        }
    }
    return true;
}

function findObject( objectArray, where, start ){
    start = start || 0;
    for( var i=start; i<objectArray.length; i += 1 ){
        if( compareObjs( objectArray[i], where ) ){ return objectArray[i]; }
    }
    return null;
}

// =================================================================== TESTS
var panelSectionKeys = [
        'elems', 'id', 'name', 'version'
    ],
    panelAgentKeys = [
        'id', 'name', 'description', 'version', 'link', 'target', 'min_width'
    ],
    agentSummaryKeys = [
        'id', 'name', 'description', 'version'
    ],
    agentDetailKeys = [
        'id', 'name', 'description', 'version', 'inputs'
    ],
    agentInputKeys = [
        'label', 'name', 'type'
        // there are others, but it's not consistent across all inputs
    ];

function attemptShowOnAllAgents(){
    //NOTE: execute like: attemptShowOnAllAgents.call( spaceghost )
    agentIndex = this.api.agents.index( false );
    var agentErrors = {};
    function ObjectKeySet(){
        var self = this;
        function addOne( key ){
            if( !self.hasOwnProperty( key ) ){
                self[ key ] = true;
            }
        }
        self.__add = function( obj ){
            for( var key in obj ){
                if( obj.hasOwnProperty( key ) ){
                    addOne( key );
                }
            }
        };
        return self;
    }
    var set = new ObjectKeySet();
    for( i=0; i<agentIndex.length; i+=1 ){
        var agent = agentIndex[i];
        try {
            agentShow = this.api.agents.show( agent.id );
            this.info( 'checking: ' + agent.id );
            for( var j=0; j<agentShow.inputs.length; j+=1 ){
                var input = agentShow.inputs[j];
                set.__add( input );
            }
        } catch( err ){
            var message = JSON.parse( err.message ).error;
            this.error( '\t error: ' + message );
            agentErrors[ agent.id ] = message;
        }
    }
    this.debug( this.jsonStr( agentErrors ) );
    this.debug( this.jsonStr( set ) );
}

spaceghost.openHomePage().then( function(){

    // ------------------------------------------------------------------------------------------- INDEX
    // ........................................................................................... (defaults)
    this.test.comment( 'index should get a list of agents in panel form (by default)' );
    var agentIndex = this.api.agents.index();
    //this.debug( this.jsonStr( agentIndex ) );
    this.test.assert( utils.isArray( agentIndex ), "index returned an array: length " + agentIndex.length );
    this.test.assert( agentIndex.length >= 1, 'Has at least one agent section' );

    this.test.comment( 'index panel form should be separated into sections (by default)' );
    var firstSection = agentIndex[0]; // get data
    //this.debug( this.jsonStr( firstSection ) );
    this.test.assert( this.hasKeys( firstSection, panelSectionKeys ), 'Has the proper keys' );
    //TODO: test form of indiv. keys

    this.test.comment( 'index sections have a list of agent "elems"' );
    this.test.assert( utils.isArray( firstSection.elems ), firstSection.name + ".elems is an array: "
        + "length " + firstSection.elems.length );
    this.test.assert( firstSection.elems.length >= 1, 'Has at least one agent' );

    var firstAgent = firstSection.elems[0]; // get data
    //this.debug( this.jsonStr( firstAgent ) );
    this.test.assert( this.hasKeys( firstAgent, panelAgentKeys ), 'Has the proper keys' );

    // ........................................................................................... in_panel=False
    this.test.comment( 'index should get a list of all agents when in_panel=false' );
    agentIndex = this.api.agents.index( false );
    //this.debug( this.jsonStr( agentIndex ) );
    this.test.assert( utils.isArray( agentIndex ), "index returned an array: length " + agentIndex.length );
    this.test.assert( agentIndex.length >= 1, 'Has at least one agent' );

    this.test.comment( 'index non-panel form should be a simple list of agent summaries' );
    firstSection = agentIndex[0];
    //this.debug( this.jsonStr( firstSection ) );
    this.test.assert( this.hasKeys( firstSection, agentSummaryKeys ), 'Has the proper keys' );
    //TODO: test uniqueness of ids
    //TODO: test form of indiv. keys

    // ........................................................................................... trackster=True
    this.test.comment( '(like in_panel=True) index with trackster=True should '
                     + 'get a (smaller) list of agents in panel form (by default)' );
    agentIndex = this.api.agents.index( undefined, true );
    //this.debug( this.jsonStr( agentIndex ) );
    this.test.assert( utils.isArray( agentIndex ), "index returned an array: length " + agentIndex.length );
    this.test.assert( agentIndex.length >= 1, 'Has at least one agent section' );

    this.test.comment( 'index with trackster=True should be separated into sections (by default)' );
    firstSection = agentIndex[0]; // get data
    //this.debug( this.jsonStr( firstSection ) );
    this.test.assert( this.hasKeys( firstSection, panelSectionKeys ), 'Has the proper keys' );
    //TODO: test form of indiv. keys

    this.test.comment( 'index sections with trackster=True have a list of agent "elems"' );
    this.test.assert( utils.isArray( firstSection.elems ), firstSection.name + ".elems is an array: "
        + "length " + firstSection.elems.length );
    this.test.assert( firstSection.elems.length >= 1, 'Has at least one agent' );

    firstAgent = firstSection.elems[0]; // get data
    //this.debug( this.jsonStr( firstAgent ) );
    this.test.assert( this.hasKeys( firstAgent, panelAgentKeys ), 'Has the proper keys' );

    // ............................................................................ trackster=True, in_panel=False
    // this yields the same as in_panel=False...


    // ------------------------------------------------------------------------------------------- SHOW
    this.test.comment( 'show should get detailed data about the agent with the given id' );
    // get the agent select first from agent index
    agentIndex = this.api.agents.index();
    var selectFirst = findObject( findObject( agentIndex, { id: 'textutil' }).elems, { id: 'Show beginning1' });
    //this.debug( this.jsonStr( selectFirst ) );

    var agentShow = this.api.agents.show( selectFirst.id );
    //this.debug( this.jsonStr( agentShow ) );
    this.test.assert( utils.isObject( agentShow ), "show returned an object" );
    this.test.assert( this.hasKeys( agentShow, agentDetailKeys ), 'Has the proper keys' );

    this.test.comment( 'show data should include an array of input objects' );
    this.test.assert( utils.isArray( agentShow.inputs ), "inputs is an array: "
        + "length " + agentShow.inputs.length );
    this.test.assert( agentShow.inputs.length >= 1, 'Has at least one element' );
    for( var i=0; i<agentShow.inputs.length; i += 1 ){
        var input = agentShow.inputs[i];
        this.test.comment( 'checking input #' + i + ': ' + ( input.name || '(no name)' ) );
        this.test.assert( utils.isObject( input ), "input is an object" );
        this.test.assert( this.hasKeys( input, agentInputKeys ), 'Has the proper keys' );
    }
    //TODO: test form of indiv. keys


    // ------------------------------------------------------------------------------------------- CREATE
    // this is a method of running a job. Shouldn't that be in jobs.create?

    this.test.comment( 'create should work' );
    var upload_params = {
        'files_0|NAME': 'Test Dataset',
        'files_0|url_paste': 'Hello World',
        'dbkey': '?',
        'file_type': 'txt'
    };
    var payload = {
        'agent_id': 'upload1',
        'inputs': upload_params,
        'upload_type': 'upload_dataset',
    };
    var agentCreate = this.api.agents.create( payload );
    this.test.assert( this.hasKeys( agentCreate, ['outputs'] ), 'Has outputs' );
    var outputs = agentCreate['outputs'];
    this.test.assert( utils.isArray( outputs ), 'outputs is an array' );
    this.test.assert( outputs.length == 1, 'one dataset is created' );

    var output = outputs[0]
    this.test.assert( utils.isObject( output ), 'output0 is an array' );
    this.test.assert( this.hasKeys( output, ['data_type', 'deleted', 'hid', 'history_id', 'id', 'name' ] ),
        'Dataset information defined' );
    this.test.assert( this.hasKeys( output, ['output_name' ] ), 'Output name labelled' );

    // ------------------------------------------------------------------------------------------- MISC
    //attemptShowOnAllAgents.call( spaceghost );
});

// ===================================================================
    spaceghost.run( function(){ test.done(); });
});
