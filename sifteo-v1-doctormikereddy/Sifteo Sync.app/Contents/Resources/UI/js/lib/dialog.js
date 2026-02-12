define(['overlay',
        'view',
        'render',
        'class'],
function(Overlay, View, render, clazz) {
  
  // TODO: Implement support for effects.
  
  function Dialog(el, options) {
    options = options || {};
    Dialog.super_.call(this, el, options);
    this._bodySel = options.bodySelector || options.contentSelector || '.body';
    this._autoRemove = options.autoRemove !== undefined ? options.autoRemove : true;
    
    var self = this
      , el = this.el;
    el.find('.close').on('click', function(){
      self.emit('close');
      self.hide();
      return false;
    });
    this.on('escape', this.hide.bind(this, true));
  }
  clazz.inherits(Dialog, View);
  
  Dialog.prototype.body =
  Dialog.prototype.content = function(el) {
    this.el.find(this._bodySel).empty().append(el);
    return this;
  };
  
  Dialog.prototype.overlay = function(options) {
    options = options || {};
    options.autoRemove = this._autoRemove;
    var self = this
      , template = options.template || 'overlay';
    this.el.addClass('modal');
    this._overlay = new Overlay(template, options);
    this._overlay.on('hide', function(){
      if (self._autoRemove) self._overlay = null;
      self.hide();
    });
    return this;
  };
  
  Dialog.prototype.escapable = function() {
    this._onkeydown = keydown.bind(this);
    
    function keydown(e) {
      if (27 != e.which) return true;
      this.emit('escape');
      return false;
    }
  };
  
  Dialog.prototype.show = function() {
    var el = this.el
      , overlay = this._overlay;
    this.emit('show');
    if (this._onkeydown) render.$(document).on('keydown', this._onkeydown);
    if (overlay) overlay.show();
    el.appendTo(document.body);
    el.removeClass('hide');
    return this;
  }
  
  Dialog.prototype.hide = function(esc) {
    var overlay = this._overlay;
    this.emit('hide');
    if (this._onkeydown) render.$(document).off('keydown', this._onkeydown);
    this.el.addClass('hide');
    if (esc && overlay) overlay.hide();
    if (this._autoRemove) {
      var self = this;
      setTimeout(function() {
        self.remove();
        self.dispose();
      }, 10);
    }
    return this;
  }
  
  Dialog.prototype.remove = function() {
    if (this._overlay) this._overlay.remove();
    return Dialog.super_.prototype.remove.call(this);
  };
  
  return Dialog;
});
