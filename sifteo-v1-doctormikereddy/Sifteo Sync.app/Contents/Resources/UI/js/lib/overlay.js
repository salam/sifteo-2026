define(['view',
        'class'],
function(View, clazz) {
  
  function Overlay(el, options) {
    options = options || {};
    Overlay.super_.call(this, el, options);
    this.closable = options.closable;
    this._autoRemove = options.autoRemove !== undefined ? options.autoRemove : true;
    
    var self = this;
    if (this.closable) {
      this.el.on('click', function() {
        self.hide();
        return false;
      });
    }
  }
  clazz.inherits(Overlay, View);
  
  Overlay.prototype.show = function() {
    this.emit('show');
    this.el.appendTo(document.body);
    this.el.removeClass('hide');
    return this;
  }
  
  Overlay.prototype.hide = function() {
    this.emit('hide');
    this.el.addClass('hide');
    if (this._autoRemove) {
      var self = this;
      setTimeout(function() {
        self.remove();
        self.dispose();
      }, 10);
    }
    return this;
  }
  
  return Overlay;
});
