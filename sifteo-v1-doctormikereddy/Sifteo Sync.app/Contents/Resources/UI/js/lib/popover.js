define(['overlay',
        'tip',
        'class'],
function(Overlay, Tip, clazz) {
  
  function Popover(el, options) {
    options = options || {};
    options.className = options.className || 'popover';
    Popover.super_.call(this, el, options);
    
    var self = this
      , el = this.el;
    el.find('.close').on('click', function(){
      self.emit('close');
      self.hide(0, true);
      return false;
    });
  }
  clazz.inherits(Popover, Tip);
  
  Popover.prototype.overlay = function(options) {
    options = options || {};
    options.autoRemove = this._autoRemove;
    var self = this
      , template = options.template || 'overlay';
    this._overlay = new Overlay(template, options);
    this._overlay.on('hide', function() {
      if (self._autoRemove) self._overlay = null;
      self.hide();
      return true;
    });
    return this;
  };
  
  Popover.prototype.show = function(el) {
    if (this._overlay) this._overlay.show();
    Popover.super_.prototype.show.call(this, el);
  }
  
  Popover.prototype.hide = function(ms, btn) {
    if (btn) {
      if (this._overlay) this._overlay.hide();
    }
    Popover.super_.prototype.hide.call(this, ms);
  }
  
  Popover.prototype.remove = function() {
    if (this._overlay) this._overlay.remove();
    return Popover.super_.prototype.remove.call(this);
  };
  
  Popover.prototype.dispose = function() {
    if (this._overlay) this._overlay.dispose();
    return Popover.super_.prototype.dispose.call(this);
  };
  
  return Popover;
});
