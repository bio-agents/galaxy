// =================================================================== module object, exports
/** Creates a new agents module object.
 *  @exported
 */
exports.create = function createAgents( spaceghost ){
    return new Agents( spaceghost );
};

/** Agents object constructor.
 *  @param {SpaceGhost} spaceghost a spaceghost instance
 */
var Agents = function Agents( spaceghost ){
    //??: circ ref?
    this.options = {};
    /** Default amount of ms to wait for upload to finish */
    this.options.defaultUploadWait = ( 45 * 1000 );
    this.spaceghost = spaceghost;
};
exports.Agents = Agents;

Agents.prototype.toString = function toString(){
    return this.spaceghost + '.Agents';
};


// -------------------------------------------------------------------
/* TODO:
    move selectors from sg to here

*/
// =================================================================== INTERNAL
var require = patchRequire( require ),
    xpath = require( 'casper' ).selectXPath;

// ------------------------------------------------------------------- get avail. agents
// list available agents
//spaceghost.then( function(){
//    spaceghost.withFrame( 'galaxy_agents', function(){
//        //var availableAgents = this.fetchText( 'a.agent-link' );
//
//        var availableAgents = this.evaluate( function(){
//            //var agentTitles = __utils__.findAll( 'div.agentTitle' );
//            //return Array.prototype.map.call( agentTitles, function( e ){
//            //    //return e.innerHtml;
//            //    return e.textContent || e.innerText;
//            //}).join( '\n' );
//
//            var agentLinks = __utils__.findAll( 'a.agent-link' );
//            return Array.prototype.map.call( agentLinks, function( e ){
//                //return e.innerHtml;
//                return e.textContent || e.innerText;
//            }).join( '\n' );
//        });
//        this.debug( 'availableAgents: ' + availableAgents );
//    });
//});

/** Parses the hid and name of a new file from the agent execution donemessagelarge
 *  @param {String} doneMsgText     the text extracted from the donemessagelarge after a agent execution
 */
Agents.prototype._parseDoneMessageForAgent = function parseDoneMessageForAgent( doneMsgText ){
    //TODO: test
    var executionInfo = {};
    var textMatch = doneMsgText.match( /added to the queue:\n\n(\d+)\: (.*)\n/m );
    if( textMatch ){
        if( textMatch.length > 1 ){
            executionInfo.hid = parseInt( textMatch[1], 10 );
        }
        if( textMatch.length > 2 ){
            executionInfo.name = textMatch[2];
        }
        executionInfo.name = textMatch[2];
    }
    return executionInfo;
};

// ------------------------------------------------------------------- upload (internal)
/** Tests uploading a file.
 *      NOTE: this version does NOT throw an error on a bad upload.
 *      It is meant for testing the upload functionality and, therefore, is marked as private.
 *      Other tests should use uploadFile
 *  @param {String} filepath    the local filesystem path of the file to upload (absolute (?))
 */
Agents.prototype._uploadFile = function _uploadFile( filepath ){
    //TODO: generalize for all agents
    var spaceghost = this.spaceghost,
        uploadInfo = {};
    uploadInfo[ spaceghost.data.selectors.agents.upload.fileInput ] = filepath;

    spaceghost.openHomePage( function(){
        // load the upload agent form
        // (we can apprently click a agent label without expanding the agent container for it)
        this.click( xpath( '//a[contains(text(),"Upload File")]' ) );
        this.jumpToMain( function(){
            this.waitForSelector( 'body' );
        });
    });

    // fill in the form and click execute - wait for reload
    spaceghost.withMainPanel( function(){
        //?? no wait for page to load?
        this.fill( this.data.selectors.agents.general.form, uploadInfo, false );

        // the following throws:
        //  [error] [remote] Failed dispatching clickmouse event on xpath selector: //input[@value="Execute"]:
        //  PageError: TypeError: 'undefined' is not a function (evaluating '$(spaceghost).formSerialize()')
        // ...and yet the upload still seems to work
        this.click( xpath( this.data.selectors.agents.general.executeButton_xpath ) );

        // wait for main panel, history reload
        ////NOTE!: assumes agent execution reloads the history panel
        this.waitForMultipleNavigation( [ 'agent_runner/upload_async_message' ],
            function thenAfterUploadRefreshes(){
                // debugging
                this.jumpToMain( function(){
                    var messageInfo = this.elementInfoOrNull( this.data.selectors.messages.all );
                    this.debug( ( messageInfo )?( messageInfo.attributes['class'] + ':\n' + messageInfo.text )
                                               :( 'NO post upload message' ) );
                });
            },
            function timeoutWaitingForUploadRefreshes( urlsStillWaitingOn ){
                throw new this.GalaxyError( 'Upload Error: '
                    + 'timeout waiting for upload "' + filepath + '" refreshes: ' + urlsStillWaitingOn );
            },
            this.agents.options.defaultUploadWait
        );
    });
};

// =================================================================== API (external)
// ------------------------------------------------------------------- misc
/** get filename from filepath
 *  @param {String} filepath    (POSIX) filepath
 *  @returns {String} filename part of filepath
 */
Agents.prototype.filenameFromFilepath = function filenameFromFilepath( filepath ){
    var lastSepIndex = filepath.lastIndexOf( '/' );
    if( lastSepIndex !== -1 ){
        return filepath.slice( lastSepIndex + 1 );
    }
    return filepath;
};

// ------------------------------------------------------------------- upload (conv.)
/** Convenience function for uploading a file.
 *      callback function will be passed an uploadInfo object in the form:
 *          filepath:   the filepath of the uploaded file
 *          filename:   the filename of the uploaded file
 *          hid:        the hid of the uploaded file hda in the current history
 *          name:       the name of the uploaded file hda
 *          hdaElement: the hda DOM (casperjs form) element info object (see Casper#getElementInfo)
 *  @param {String} filepath        (POSIX) filepath relative to the script's directory
 *  @param {Function} callback      callback function called after hda moves into ok state (will be passed uploadInfo)
 *  @param {Integer} timeoutAfterMs milliseconds to wait before timing out (defaults to options.defaultUploadWait)
 */
Agents.prototype.uploadFile = function uploadFile( filepath, callback, timeoutAfterMs ){
    timeoutAfterMs = timeoutAfterMs || this.options.defaultUploadWait;
    var spaceghost = this.spaceghost,
        filename = this.filenameFromFilepath( filepath ),
        uploadInfo = {};

    spaceghost.info( 'uploading file: ' + filepath + ' (timeout after ' + timeoutAfterMs + ')' );
    this._uploadFile( filepath );

    // error if an info message wasn't found
    spaceghost.withMainPanel( function checkUploadMessage(){
        var infoInfo = spaceghost.elementInfoOrNull( this.data.selectors.messages.infolarge );
        if( ( infoInfo )
        &&  ( infoInfo.text.indexOf( this.data.text.upload.success ) !== -1 ) ){
            // safe to store these
            uploadInfo.filename = filename;
            uploadInfo.filepath = filepath;

        } else {
            // capture any other messages on the page
            var otherInfo = spaceghost.elementInfoOrNull( this.data.selectors.messages.all ),
                message   = ( otherInfo && otherInfo.text )?( otherInfo.text ):( '' );
            throw new this.GalaxyError( 'Upload Error: no success message uploading "' + filepath + '": ' + message );
        }
    });

    // the hpanel should refresh and display the uploading file, wait for that to go into the ok state
    // throw if uploaded HDA doesn't appear, or it doesn't move to 'ok' after allotted time
    //spaceghost.historypanel.waitForHdas()
    spaceghost.historypanel.waitForHda( filename,
        // success: update the upload info and run callback
        function whenInStateFn( newHdaInfo ){
            this.info( 'Upload complete: ' + newHdaInfo.text );
            uploadInfo.hdaElement = newHdaInfo;
            callback.call( spaceghost, uploadInfo );
        },
        function timeoutFn( newHdaInfo ){
            this.warning( 'timeout waiting for upload: ' + filename + ', ' + this.jsonStr( newHdaInfo ) );
            throw new spaceghost.GalaxyError( 'Upload Error: timeout waiting for ok state: '
                + '"' + uploadInfo.filepath + '" (waited ' + timeoutAfterMs + ' ms)' );
        },
        timeoutAfterMs
    );

    return spaceghost;
};
//TODO: upload via url
//TODO: upload by textarea
