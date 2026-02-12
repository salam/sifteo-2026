/**
 * render
 *
 * This module implements the rendering engine for Sail.js applications.
 * Rendering is used to construct fragments of HTML, which are inserted
 * dynamically into the DOM.
 */
define(['exports', 'module',
        'dom',
        './lib/dom/render'],
function(exports, module, DOM, Render) {
  
  /**
   * Render template `name` using given `locals`.
   *
   * By default, the rendering engine will append "-template" to the name and
   * select the HTML element with that ID in order to load the template.  For
   * example, invoking:
   *
   *     render('hello', { name: 'Dave' });
   *
   * will result in rendering the following template:
   *
   *     <script id="hello-template" type="text/template">
   *         <p>Hello, {{name}}</p>
   *     </script>
   *
   * This return value from this function can take multiple forms:
   *
   *   1. A compiled template function.  In this case, the returned function
   *      must be invoked in order to produce the fragment of HTML.
   *
   *      Returning a template function allows that function to be attached to
   *      a wrapped DOM element.  The element can then be re-rendered by
   *      invoking el.render({ name: 'Jane' }), for example.
   *
   *   2. A string containing HTML.  In this case, the returned string is used
   *      to construct a DOM element or tree.
   *
   *      This case is suitable for applications don't require re-rendering and
   *      can be used as an optimization to lower resource usage.
   *
   * Sail.js does not impose any specific template engine on the application.
   * During initialization, an application configures the template format being
   * used by registering an engine:
   *
   *     render.engine('text/template', mustache());
   *
   * @param {String} name  name of template to render
   * @param {Object} locals  local variables to insert into template
   * @return {Function|String}
   * @api public
   */
  exports = module.exports = function(name, locals) {
    var uc = _useCache
      , out;
    
    if (uc) {
      out = _cache[name];
      if (out) return out;
    }
    
    var tmpl = _load(name);
    if (typeof tmpl == 'string') {
      tmpl = { string: tmpl }
    }
    // TODO: Implement support for precompiled templates, where `_load` returns
    //       a function.
    
    var type = tmpl.type || 'default';
    var engine = _engines[type];
    if (!engine) throw new Error('No engine to render template type: ' + type);
    // TODO: Pass arbitrary number of arguments to engine.
    //return engine(tmpl.string, locals, options);
    out = engine(tmpl.string, locals);
    if (uc) _cache[name] = out;
    return out;
  };
  exports.render = exports;
  
  /**
   * Register template engine for given `type`.
   *
   * @param {String} type  type of template
   * @param {Function} fn  template engine function
   * @api public
   */
  exports.engine = function(type, fn) {
    if (typeof type == 'function') {
      fn = type;
      type = 'default';
    }
    _engines[type] = fn;
  };
  
  exports.cache = function(flag) {
    _useCache = flag;
  }
  
  /**
   * Register template loader function.
   *
   * By default, the rendering engine will load templates from the HTML document
   * by selecting based on ID.  This default was chosen because it allows
   * applications to be developed with the minimal set of tooling (ie, just a
   * text editor).
   *
   * Some developers prefer to define templates outside of the main HTML
   * document, for example by exporting strings from a JavaScript module.  In
   * this case, the template loader can be overridden to support this behavior.
   *
   *     render.loader(function(name) {
   *       return templates.name;
   *     });
   *
   * As an optimization, many deployments ship precompiled templates so as not
   * to incur the overhead on the client side.  Similarly, the template loader
   * can be overrriden to return the compiled template directly.
   *
   *     render.loader(function(name) {
   *       return compiledTemplates.name;
   *     });
   *
   * @param {Function} fn  template loader function
   * @api public
   */
  exports.loader = function(fn) {
    _load = fn;
  }
  
  /**
   * DOM utility.
   *
   * This function exposes the DOM utility in use by the application.
   *
   * Because DOM access is so pervasive within a web application, the render
   * module exposes a single entry point for this functionality.  This also
   * serves as a cheap form of dependency injection, so that the developer can
   * choose which utility to employ.  Developers of `View` modules are advised
   * to acccess the DOM through this function, rather than through their own
   * explicitly declared dependency (which may conflict with the application
   * developer's preferred choice).
   *
   * By default, the [DOM](https://github.com/anchorjs/dom) module provided by
   * Anchor is used.  However, this can be overridden to use any compatible
   * module.
   *
   * To use [jQuery](http://jquery.com/)
   *
   *     render.$(jQuery);
   *
   * To use [Zepto](http://zeptojs.com/)
   *
   *     render.$(Zepto);
   *
   * To use [Kimbo](http://kimbojs.com/)
   *
   *     render.$(Kimbo);
   *
   * To use [bonzo](https://github.com/ded/bonzo)
   *
   *     render.$(bonzo);
   *
   *
   * Anchor's DOM module defines a strict subset of DOM utility functions, which
   * are designed to be compatible with jQuery and jQuery-compatible libraries.
   * Developers of `View` modules for use with Sail.js are advised to only
   * invoke functions within this subset, so as not to create an unneccessary
   * requirement to use an alternative DOM utility.  Likewise, application
   * developers are warned that using an incomptible DOM utility may result in
   * incorrect or undefined behavior.
   *
   * @api public
   */
  exports.$ = function(nodes) {
    if (typeof nodes == 'function') {
      _$ = nodes;
      return;
    }
    return _$.apply(undefined, arguments);
  };
  
  
  // Augment the DOM with (re)rendering functionality.
  DOM.augment(Render);
  
  
  var _load = function(name) {
    var el = _$('#' + name + '-template');
    return { type: el.attr('type'), string: el.html() }
  }
  
  var _engines = {};
  var _cache = {};
  var _useCache = true;
  
  var _$ = DOM;
});
