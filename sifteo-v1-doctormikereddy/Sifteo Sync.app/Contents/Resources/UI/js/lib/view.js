define(['render',
        'events',
        'class'],
function(render, Emitter, clazz) {
  
  function View(el, options) {
    View.super_.call(this);
    
    if (typeof el == 'string') {
      var out = render.render(el, options);
      if (typeof out == 'string') {
        this.el = render.$(out);
      } else if (typeof out == 'function') {
        this.el = render.$(out(options));
      }
    } else {
      this.el = el;
    }
  }
  clazz.inherits(View, Emitter);
  
  View.prototype.remove = function() {
    this.el.remove();
    return this;
  }
  
  View.prototype.dispose = function() {
    this.removeAllListeners();
  }
  
  return View;
});
