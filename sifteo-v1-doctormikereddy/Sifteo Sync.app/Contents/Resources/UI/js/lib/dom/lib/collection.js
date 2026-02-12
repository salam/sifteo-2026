/**
 * Module definition.
 */
define(function() {
  
  /**
   * `Collection` constructor.
   *
   * This class represents a collection of DOM elements.  A collection can
   * contain one or more elements, and may be empty.  In many cases, a
   * collection will contain a single element, in which case it can be logically
   * thought of as the element itself rather than a collection.
   *
   * `Collection` has a number of functions that simplify operations on the DOM.
   * When these functions are invoked, they are carried out on all elements in
   * the collection.  The technique of wrapping DOM elements in a `Collection`
   * and invoking utility functions simplifies operations on the DOM.
   *
   * @api public
   */
  function Collection(nodes) {
    this.length = 0;
    if (nodes) {
      // cast a single node to an array
      nodes = nodes.nodeType ? [nodes] : nodes;
      this.length = nodes.length;
      // add each node to an index-based property on collection, in order to
      // appear "array"-like
      for (var i = 0, len = nodes.length; i < len; i++) {
        this[i] = nodes[i];
      }
    }
  }
  
  /**
   * Iterate over DOM element collection, executing a function for each element.
   *
   * `fn` is invoked with three arguments:
   *   - the element
   *   - the index of the element
   *   - the collection being iterated over
   *
   * `each()` is aliased to `forEach()` in order to appear `Array`-like.
   *
   * Examples:
   *
   *     col.each(function(el) {
   *       // ...
   *     });
   *
   *     col.each(function(el, i) {
   *       // ...
   *     }, this);
   *
   *
   * Transition from jQuery or Zepto:
   *
   * This function provides similar functionality to jQuery's `each()`, but
   * differs in the order of the arguments passed to `fn`.  In jQuery, the index
   * is the first argument and the element is the second argument.  In Anchor,
   * this order is swapped.  Additionally, in jQuery `this` always refers to the
   * element; whereas in Anchor `this` is determined by `scope`.
   *
   * These differences are intentional, and in conformance to the ECMAScript 5
   * standard for `Array#forEach`.
   *
   * Transition from Ender/Bonzo:
   *
   * This function is compatible with Bonzo, with the caveat that `forEach` is
   * not aliased by Bonzo.
   *
   *
   * @param {Function} fn Function to execute for each element.
   * @param {Object} scope Object to use as `this` when executing `fn`.
   * @return {Collection} for chaining
   * @api public
   */
  Collection.prototype.each =
  Collection.prototype.forEach = function(fn, scope) {
    for (var i = 0, len = this.length; i < len; i++) {
      fn.call(scope, this[i], i, this);
    }
    return this;
  }
  
  /**
   * Iterate over DOM element collection, creating a new array with the results
   * of executing a function for each element.
   *
   * `fn` is invoked with three arguments:
   *   - the element
   *   - the index of the element
   *   - the collection being iterated over
   *
   * If `fn` returns `undefined`, the result will not be added to the mapped
   * array.
   *
   *
   * Transition from jQuery or Zepto:
   *
   * This function provides similar functionality to jQuery's `map()`, but
   * differs in the order of the arguments passed to `fn`.  In jQuery, the index
   * is the first argument and the element is the second argument.  In Anchor,
   * this order is swapped.  Additionally, in jQuery `this` always refers to the
   * element; whereas in Anchor `this` is determined by `scope`.  Furthermore,
   * jQuery returns a jQuery object, whereas this function returns a standard
   * array.
   *
   * These differences are intentional, and in conformance to the ECMAScript 5
   * standard for `Array#map`.
   *
   * Transition from Ender/Bonzo:
   *
   * This function is generally compatible with Bonzo.  However, Bonzo does not
   * provide a facility for setting `scope`.  Furthermore, `Bonzo` accepts an
   * optional `reject` function to control which results are not added to the
   * mapped array.
   *
   *
   * @param {Function} fn Function to execute for each element.
   * @param {Object} scope Object to use as `this` when executing `fn`.
   * @return {Array}
   * @api public
   */
  Collection.prototype.map = function(fn, scope) {
    var m = [], n;
    for (var i = 0, len = this.length; i < len; i++) {
      n = fn.call(scope, this[i], i, this);
      if (n !== undefined) m.push(n);
    }
    return m;
  }
  
  return Collection;
});
