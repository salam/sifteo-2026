define(['dib',
        'events',
        'class'],
function(Dib, Emitter, clazz) {
  
  function Controller() {
    Emitter.call(this);
    this._init();
  }
  clazz.inherits(Controller, Emitter);
  
  Controller.prototype._init = function() {
    var dib = new Dib(this.template)
      , locals = this.willLoadDib()
      , element;
    
    if (this.tagName || this.className || this.attributes || this.id) {
      element = {}
      element.tag = this.tagName || 'div';
      element.attrs = this.attributes || {};
      if (this.id) element.attrs['id'] = this.id;
      if (this.className) element.attrs['class'] = this.className;
    }
    
    dib.container(element)
       .events(this.events, this);
       
    // TODO: Implement support in `Dib` for automatically instantiating views,
    //       which will work similarly to automatic event binding.
    
    this.el = dib.create(locals);
    this.didLoadDib();
  }
  
  Controller.prototype.willLoadDib = function() {};
  Controller.prototype.didLoadDib = function() {};
  Controller.prototype.willAddEl = function() {};
  Controller.prototype.didAddEl = function() {};
  Controller.prototype.willRemoveEl = function() {};
  Controller.prototype.didRemoveEl = function() {};
  
  return Controller;
});
