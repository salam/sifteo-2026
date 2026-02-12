define({
  
  /**
   * Display the matched elements.
   *
   * Examples:
   *
   *     $('.target').show();
   *
   *
   * Transition from jQuery or Zepto:
   *
   * This function does not support the animation effects provided by jQuery and
   * Zepto.  It is otherwise compatible.
   * 
   * Transition from Ender/Bonzo:
   *
   * This function is compatible with Bonzo.
   *
   *
   * @return {Collection} for chaining
   */
  show: function(val) {
    return this.each(function(el) {
      el.style.display = val || '';
    });
  },
  
  /**
   * Hide the matched elements.
   *
   * Examples:
   *
   *     $('.target').hide();
   *
   *
   * Transition from jQuery or Zepto:
   *
   * This function does not support the animation effects provided by jQuery and
   * Zepto.  It is otherwise compatible.
   * 
   * Transition from Ender/Bonzo:
   *
   * This function is compatible with Bonzo.
   *
   *
   * @return {Collection} for chaining
   */
  hide: function() {
    return this.each(function(el) {
      el.style.display = 'none';
    });
  },
  
  css: function()  {
  }
  
});
