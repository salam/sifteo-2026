define(function() {
  function CloudRequestError(message, code, resObj) {
    this.name = 'CloudRequestError';
    this.message = message || 'Failed to complete request';
    this.code = code;
    this.responseObject = resObj;
  }
  CloudRequestError.prototype = new Error();
  CloudRequestError.prototype.constructor = CloudRequestError;
  
  return CloudRequestError;
});
