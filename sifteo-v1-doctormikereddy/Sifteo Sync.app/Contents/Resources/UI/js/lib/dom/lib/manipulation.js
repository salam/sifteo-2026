define({
  
  /**
   * Get the HTML contents of the first element in the set of matched elements.
   *
   * Returns `null` if the set is empty.
   *
   * Examples:
   *
   *     $('#message').html();
   *
   *
   * Sets the HTML contents of each element in the set of matched elements.
   *
   * Examples:
   *
   *     $('#message').html('<b>Welcome!</b>');
   *
   *
   * Transition from jQuery or Zepto:
   *
   * This function is compatible with jQuery and Zepto.
   *
   * Transition from Ender/Bonzo:
   *
   * This function returns `null` when called as a getter against a set
   * containing multiple elements, whereas Bonzo returns an empty string.
   *
   *
   * @param {String} html
   * @return {String|Collection}
   * @api public
   */
  html: function(html) {
    // TODO: Call empty before setting innerHTML.
    return html === undefined ?
      (this[0] ? this[0].innerHTML : null) :
      this.each(function(el) {
        el.innerHTML = html;
      });
  },
  
  /**
   * Get the text contents of the first element in the set of matched elements.
   *
   * Returns `null` if the set is empty.
   *
   * Examples:
   *
   *     $('#message').text();
   *
   *
   * Sets the text contents of each element in the set of matched elements.
   *
   * Examples:
   *
   *     $('#message').text('Welcome!');
   *
   *
   * Transition from jQuery or Zepto:
   *
   * This function differs from jQuery in that it returns the text of only the
   * first element in a set containing multiple elements.  jQuery concatenates
   * the text of each element in a multiple element set.
   *
   * This function is compatible with Zepto, which returns the text of only the
   * first element in a set containing multiple elements.
   *
   * Transition from Ender/Bonzo:
   *
   * This function returns `null` when called as a getter against a set
   * containing multiple elements, whereas Bonzo returns an empty string.
   *
   *
   * @param {String} text
   * @return {String|Collection}
   * @api public
   */
  text: function(text) {
    return text === undefined ?
      (this[0] ? this[0].textContent : null) :
      this.each(function(el) {
        el.textContent = text;
      });
  },
  
  append: function(c) {
    return this.each(function(el) {
      el.appendChild(c);
    });
  }
  
});
