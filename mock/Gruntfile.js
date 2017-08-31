'use strict';

var path = require('path');
var mockApi = require('swagger-mock-api');

module.exports = function(grunt) {

  grunt.initConfig({
    connect: {
      server: {
        options: {
          hostname: 'localhost',
          keepalive: true,
          middleware: function(connect, options, middlewares) {
            middlewares.unshift(mockApi({
              swaggerFile: path.join(__dirname, '../swagger.yaml'),
              watch: true // enable reloading the routes and schemas when the swagger file changes
            }));
            middlewares.unshift(function(req, res, next) {
              res.setHeader('Access-Control-Allow-Origin', '*');
              res.setHeader('Access-Control-Allow-Methods', '*');
              next();
            });
            return middlewares;
          }
        }
      }
    }
  });


  grunt.loadNpmTasks('grunt-contrib-connect');

  grunt.registerTask('default', ['connect']);
};
