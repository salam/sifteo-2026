define(['exports', 'module'],
function(exports, module) {

  exports = module.exports = function(methods, options) {
    options = options || {};
    
    var service = new Object();
    service.listMethods = function(result) {
      var m = [];
      for (var name in methods) {
        m.push(name);
      }
      return result(null, m);
    }
    
    service.methodSignature = function(name, result) {
      var method = methods[name];
      if (!method) return result(new Error('requested method not found'))
      
      var s = 'undef';
      if (method.signature) {
        s = [ method.signature ];
      } else if (method.signatures) {
        s = method.signatures;
      }
      return result(null, s);
    }
    
    service.methodHelp = function(name, result) {
      var method = methods[name];
      if (!method) return result(new Error('requested method not found'))
      
      return result(null, method.help || options.help || ('No help for ' + name));
    }
    
    return service;
  }
});

