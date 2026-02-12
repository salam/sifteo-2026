define(['view',
        'render',
        'class'],
function(View, render, clazz) {
  
  function Wizard(el, options) {
    options = options || {};
    Wizard.super_.call(this, el, options);
    this._bodySel = options.bodySelector || '.body';
    this._steps = [];
    this._i = 0;
    this._attachedTo = null;
    
    var self = this
      , el = this.el;
    
    el.find('.prev').addClass('disabled');
    el.find('.prev').on('click', function() {
      if (el.find('.prev').hasClass('disabled')) return false;
      self.prev(true);
      return false;
    });
    if (options.form === false) {
      // By default, `Wizard` expects to be attached to a form, and will advance
      // to the next step on submit events.  Set `form` option to `false` to
      // override this behavior.
      el.find('.next').on('click', function() {
        if (el.find('.next').hasClass('disabled')) return false;
        self.next(true);
        return false;
      });
    }
  }
  clazz.inherits(Wizard, View);
  
  Wizard.prototype.remove = function() {
    return Wizard.super_.prototype.remove.call(this);
  }
  
  Wizard.prototype.attach = function(id) {
    if (this._attachedTo) return;
    this._attachedTo = id;
    
    var self = this
      , el = this.el;
    render.$(id).on('submit', function(e) {
      if (el.find('.next').hasClass('disabled')) return false;
      self.next(true);
      return false;
    })
  }
  
  Wizard.prototype.step = function(name, el, options) {
    if (typeof name != 'string') {
      options = el;
      el = name;
      name = undefined;
    }
    options = options || {};
    options.prevable = options.prevable !== undefined ? options.prevable : true;
    options.nextable = options.nextable !== undefined ? options.nextable : true;
    
    if (this._steps.length) el.addClass('hide');
    this.el.find(this._bodySel).append(el);
    this._steps.push({ el: el, name: name, opts: options });
    return this;
  };
  
  Wizard.prototype.next = function(ask) {
    if (this._i >= this._steps.length) throw new Error('index out of range');
    var step = this._steps[this._i]
      , fin = this._i == this._steps.length - 1 ? true : step.opts.final;
    if (fin) { this.emit('done', step.name, this._i); return; }
    var go = (ask && this.delegate && this.delegate.willNext) ? this.delegate.willNext(step.name, this._i) : true;
    if (go) this._goto(this._i + 1, this._i);
  }
  
  Wizard.prototype.prev = function(ask) {
    if (this._i == 0) return;
    var step = this._steps[this._i];
    var go = (ask && this.delegate && this.delegate.willPrev) ? this.delegate.willPrev(step.name, this._i) : true;
    if (go === false) {
      return;
    } else if (go === true) {
      go = this._i - 1;
    } else if (typeof go == 'string') {
      for (var i = 0, len = this._steps.length; i < len; i++) {
        if (this._steps[i].name == go) { go = i; break; }
      }
    }
    
    this._goto(go, this._i);
  }
  
  Wizard.prototype.to = function(step) {
    var i;
    if (typeof step == 'number') {
      i = step;
    } else if (typeof step == 'string') {
      for (var ix = 0, len = this._steps.length; ix < len; ix++) {
        if (this._steps[ix].name == step) { i = ix; break; }
      }
    }
    if (i == undefined) throw new Error('invalid argument');
    this._goto(i, this._i);
  }
  
  Wizard.prototype._goto = function(i, pi) {
    this._i = i;
    var step = this._steps[i]
      , prevable = i == 0 ? false : step.opts.prevable
      , nextable = step.opts.nextable;
    this.emit('step', step.name, i);
    this._steps[pi].el.addClass('hide');
    this._steps[i].el.removeClass('hide');

    if (prevable) this.el.find('.prev').removeClass('disabled');
    else this.el.find('.prev').addClass('disabled');
    if (nextable) this.el.find('.next').removeClass('disabled');
    else this.el.find('.next').addClass('disabled');

    this.emit('stepped', step.name, i);
  }
  
  return Wizard;
});
