define(['exports'],
function(exports) {
  
  function addEventListener(type, listener, useCapture) {
    return this.forEach(function(el) {
      el.addEventListener(type, listener, useCapture);
    });
  }
  
  function removeEventListener(type, listener, useCapture) {
    return this.forEach(function(el) {
      el.removeEventListener(type, listener, useCapture);
    });
  }
  
  exports.on =
  exports.addListener =
  exports.addEventListener = addEventListener;
  exports.off =
  exports.removeListener =
  exports.removeEventListener = removeEventListener;
});
