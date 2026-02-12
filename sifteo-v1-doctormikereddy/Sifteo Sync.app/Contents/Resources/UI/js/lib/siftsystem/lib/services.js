define(function() {
  
  function Services() {
  }
  
  Services.prototype.open = function(url) {
    siftSystem.services.open(url);
  }
  
  return new Services();
});
