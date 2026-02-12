define(function() {
  
  // TODO: Need to be able to select from wrapped DOM elements.
  function select(selector, el) {
    return (el || document).querySelectorAll(selector);
  }
  
  return select;
});
