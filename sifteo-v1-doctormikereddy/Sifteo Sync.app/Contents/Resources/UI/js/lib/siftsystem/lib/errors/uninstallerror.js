define(function() {
  function UninstallError(message, code) {
    this.name = 'UninstallError';
    this.message = message || 'Failed to uninstall app';
    this.code = code;
  }
  UninstallError.prototype = new Error();
  UninstallError.prototype.constructor = UninstallError;
  
  return UninstallError;
});
