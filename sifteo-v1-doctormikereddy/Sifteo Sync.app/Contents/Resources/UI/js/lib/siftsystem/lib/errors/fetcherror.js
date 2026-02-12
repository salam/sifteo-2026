define(function() {
  function FetchError(message, code) {
    this.name = 'FetchError';
    this.message = message || 'Failed to download app';
    this.code = code;
  }
  FetchError.prototype = new Error();
  FetchError.prototype.constructor = FetchError;
  
  return FetchError;
});
