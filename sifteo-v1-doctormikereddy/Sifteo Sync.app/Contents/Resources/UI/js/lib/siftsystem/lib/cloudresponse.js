define(['events',
        'class'],
function(Emitter, clazz) {
  
  function CloudResponse() {
    CloudResponse.super_.call(this);
  }
  clazz.inherits(CloudResponse, Emitter);
  
  CloudResponse.prototype._end = function(creq) {
    this.responseObject = creq.responseObject;
    this.emit('end');
  };
  
  return CloudResponse;
});
