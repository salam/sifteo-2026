define(['./maincontroller',
        'render',
        'render-mustache',
        'jquery',
        'bootstrap'],
function(MainController, render, mustache, jQuery, _bootstrap) {
  
  
  // jQuery rendering support.
  jQuery.fn.render = function(locals, options) {
    var html = this._template(locals, options);
    return this.html(html);
  };
  
  render.engine('text/template', mustache());
  render.$(jQuery);
  
  jQuery(function() {
    var mc = new MainController();
    mc.run();
  });
});
