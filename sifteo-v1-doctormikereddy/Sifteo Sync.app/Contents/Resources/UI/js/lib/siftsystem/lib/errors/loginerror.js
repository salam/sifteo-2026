define(function() {
  function LogInError(message, code) {
    this.name = 'LogInError';
    this.message = message || 'Failed to log in';
    this.code = code;
  }
  LogInError.prototype = new Error();
  LogInError.prototype.constructor = LogInError;
  
  return LogInError;
});
