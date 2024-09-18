module.exports = function(grunt) {
    "use strict";

    var GALAXY_PATHS = {
            dist        : '../static/scripts',
            maps        : '../static/maps',
            // this symlink allows us to serve uncompressed scripts in DEV_PATH for use with sourcemaps
            srcSymlink  : '../static/src',
        },
        TOOLSHED_PATHS = {
            dist        : '../static/agentshed/scripts',
            maps        : '../static/agentshed/maps',
            srcSymlink  : '../static/agentshed/src',
        };

    grunt.config.set( 'app', 'galaxy' );
    grunt.config.set( 'paths', GALAXY_PATHS );
    if( grunt.option( 'app' ) === 'agentshed' ){
	    grunt.config.set( 'app', grunt.option( 'app' ) );
	    grunt.config.set( 'paths', TOOLSHED_PATHS );
    }

    grunt.loadNpmTasks('grunt-check-modules');
    // see the sub directory grunt-tasks/ for individual task definitions
    grunt.loadTasks( 'grunt-tasks' );
    // note: 'handlebars' *not* 'templates' since handlebars doesn't call uglify
    grunt.registerTask( 'default', [ 'check-modules', 'uglify', 'webpack' ] );
};
