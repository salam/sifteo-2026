define(['jquery'],
function($) {
  return function(options) {
    options = options || {};
    
    function hideOverlays(result) {
      $('.actions').hide();
      $('#selector').hide();
      return result();
    }
    
    function showOverlays(result) {
      $('.actions').show();
      $('#selector').show();
      return result();
    }
    
    var service = new Object();
    service.hideOverlays = hideOverlays;
    service.showOverlays = showOverlays;
    return service;
  }
});
