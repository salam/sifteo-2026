define(function() {
  function UnpairError(message, code) {
    this.name = 'UnpairError';
    this.message = message || 'Failed to unpair cubes';
    this.code = code;
  }
  UnpairError.prototype = new Error();
  UnpairError.prototype.constructor = UnpairError;
  
  return UnpairError;
});
