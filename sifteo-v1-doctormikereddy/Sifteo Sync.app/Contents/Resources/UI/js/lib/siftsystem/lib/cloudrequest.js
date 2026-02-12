define(['./cloudresponse',
        './errors/cloudrequesterror',
        'events',
        'class'],
function(CloudResponse, CloudRequestError, Emitter, clazz) {
  
  function CloudRequest(path, method) {
    CloudRequest.super_.call(this);
    this.path = path;
    this.method = method || 'GET';
  }
  clazz.inherits(CloudRequest, Emitter);
  
  CloudRequest.prototype.send = function(obj) {
    var self = this
      , creq = siftSystem.cloud.request(this.method, this.path)
      , res;
    creq.onsuccess.connect(function() {
      res = new CloudResponse();
      self.emit('response', res);
      res._end(creq);
    });
    creq.onerror.connect(function(code, message) {
      self.emit('error', new CloudRequestError(message, code, creq.responseObject));
    });
    creq.send(obj);
  }
  
  return CloudRequest;
});
