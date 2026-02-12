define(['exports', 'module'],
function(exports, module) {

  exports = module.exports = function(caps) {
  
    var service = new Object();
    service.getCapabilities = function(result) {
      var c = {};
      for (var id in caps) {
        var cap = caps[id];
        c[id] = { specUrl: cap.url, specVersion: cap.version };
      }
      return result(null, c);
    }
    
    return service;
  }
});

