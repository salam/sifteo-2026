define(['./cloudrequest'],
function(CloudRequest) {
  
  function Cloud() {
  }
  
  Cloud.prototype.request = function(path, method, cb) {
    if (typeof method == 'function') {
      cb = method;
      method = 'GET';
    }
    
    var req = new CloudRequest(path, method);
    if (cb) req.on('response', cb);
    return req;
  }
  
  Cloud.prototype.get = function(path, cb) {
    var req = this.request(path, 'GET', cb);
    req.send();
    return req;
  }
  
  Cloud.prototype.post = function(obj, path, cb) {
    var req = this.request(path, 'POST', cb);
    req.send(obj);
    return req;
  }
  
  Cloud.prototype.put = function(obj, path, cb) {
    var req = this.request(path, 'PUT', cb);
    req.send(obj);
    return req;
  }
  
  return new Cloud();
});
