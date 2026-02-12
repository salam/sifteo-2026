define(function() {
  function InstallError(message, code) {
    this.name = 'InstallError';
    this.message = message || 'Failed to install app';
    this.code = code;
  }
  InstallError.prototype = new Error();
  InstallError.prototype.constructor = InstallError;
  
  return InstallError;
});
