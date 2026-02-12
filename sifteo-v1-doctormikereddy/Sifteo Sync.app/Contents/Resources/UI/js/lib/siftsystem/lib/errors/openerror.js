define(function() {
  function OpenError(message, code) {
    this.name = 'OpenError';
    this.message = message || 'Failed to open app';
    this.code = code;
  }
  OpenError.prototype = new Error();
  OpenError.prototype.constructor = OpenError;
  
  return OpenError;
});
