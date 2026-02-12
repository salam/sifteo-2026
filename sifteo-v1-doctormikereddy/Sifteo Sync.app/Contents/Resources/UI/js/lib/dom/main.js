/**
 * dom
 *
 * This module provides DOM utility functions for simplifying common DOM
 * operations, including traversal, manipulation, etc.
 */
define(['./lib/collection',
        './lib/traversal',
        './lib/manipulation',
        './lib/metrics',
        './lib/style',
        './lib/events',
        'selector',
        'class'],
function(Collection, Traversal, Manipulation, Metrics, Style, Events, select, clazz) {
  
  /**
   * Augment `Collection` with DOM utility functions.
   */
  clazz.augment(Collection, Traversal);
  clazz.augment(Collection, Manipulation);
  clazz.augment(Collection, Metrics);
  clazz.augment(Collection, Style);
  clazz.augment(Collection, Events);
  
  /**
   * Returns a collection of DOM elements with usable utility functions.
   *
   * @param {Mixed} nodes
   * @return {Collection}
   * @api public
   */
  function dom(nodes) {
    // TODO: Document the various ways of using this function.
    
    if (nodes instanceof Collection) return nodes;
    if (typeof nodes == 'string') {
      if (/^\s*<([^\s>]+)/.test(nodes)) {
        // HTML fragment
        nodes = dom.fragment(nodes);
      } else {
        // CSS selector
        nodes = select(nodes)
      }
    }
    return new Collection(nodes);
  }
  
  /**
   * Creates a DOM element with tag and optional attributes and text.
   *
   * Examples:
   *
   *     $.create('div');
   *
   *     $.create('p', 'Hello');
   *
   *     $.create('p', { 'id': 'welcome' }, 'Hello Jared');
   *
   * @param {String} tag
   * @param {Object} attrs
   * @param {String} text
   * @return {Element} DOM element
   * @api public
   */
  dom.create = function(tag, attrs, text) {
    if (typeof attrs == 'string') {
      text = attrs;
      attrs = {};
    }
    
    var el = document.createElement(tag);
    for (var name in attrs) {
      el.setAttribute(name, attrs[name]);
    }
    if (text) el.textContent = text;
    return el;
  }
  
  /**
   * Creates a DOM element from an HTML fragment.
   *
   * @param {String} html HTML fragment.
   * @return {Array} DOM elements
   * @api public
   */
  dom.fragment = function(html) {
    var div = document.createElement('div');
    div.innerHTML = html;
    return div.childNodes;
  }
  
  /**
   * Augments DOM utilities with functions from `mixin`.
   *
   *
   * Transition from jQuery or Zepto:
   *
   * `augment()` provides functionality similiar to that used to author jQuery
   * plugins.  jQuery is extended by adding functions to `jQuery.fn`:
   *
   *     jQuery.fn.myUtility = function() { ... };
   *
   * In Anchor, this translates to:
   *
   *     $.augment({
   *       myUtility: function() { ... }
   *     });
   *
   * Transition from Ender/Bonzo:
   *
   * This function is equivalent to `bonzo.aug()`.  `bonzo.aug()` has an
   * optional `target` argument that indicates the object to augment, which
   * defaults to `Bonzo.prototype`.  In Anchor, this argument is not available;
   * the `Collection` DOM wrapper is always augmented.
   *
   *
   * @param {Object} mixin.
   * @api public
   */
  dom.augment = function(mixin) {
    clazz.augment(Collection, mixin);
    return this;
  }
  
  return dom;
});
