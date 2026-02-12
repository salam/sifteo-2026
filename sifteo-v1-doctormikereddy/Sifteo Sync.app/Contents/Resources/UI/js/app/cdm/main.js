define(['exports',
        'jsonrpc-postmessage',
        'xmlrpc-getcapabilities',
        'xmlrpc-introspect',
        './services/ui'],
function(exports, jsonrpc, getCapabilities, introspect, ui) {
  
  function listen() {
    jsonrpc.listen(function(chan) {
      chan.expose('system', getCapabilities({
        'jsonrpc': { url: 'http://json-rpc.org/wiki/specification', version: 1 },
        'introspect': { url: 'http://xmlrpc-c.sourceforge.net/xmlrpc-c/introspection.html', version: 1 },
        'sifteoSync': { url: 'http://schemas.sifteo.com/xmlrpc/sync', version: 0 }
      }));
      chan.expose('system', introspect({
        'system.getCapabilities': { signature: ['struct'] },
        'system.listMethods': { signature: ['array'] },
        'system.methodSignature': { signature: ['array', 'string'] },
        'system.methodHelp': { signature: ['string', 'string'] },
        'ui.hideOverlays': { signature: ['nil'] },
        'ui.showOverlays': { signature: ['nil'] }
      }));
      chan.expose('ui', ui());
    });
  }

  exports.listen = listen;
});
