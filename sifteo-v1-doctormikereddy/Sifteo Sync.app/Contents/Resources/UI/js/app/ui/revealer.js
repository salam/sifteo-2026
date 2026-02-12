define(['view',
        'class'],
function(View, clazz) {
  
  function Revealer(el, options) {
    options = options || {};
    Revealer.super_.call(this, el, options);
    this._csel = options.contentSelector || 'body';
    
    var self = this
      , el = this.el;
    el.find('.right').on('click', function() {
      if (el.find('.right').hasClass('disabled')) return false;
      self.emit('next');
      return false;
    });
    el.find('.left').on('click', function() {
      if (el.find('.left').hasClass('disabled')) return false;
      self.emit('prev');
      return false;
    });
  }
  clazz.inherits(Revealer, View);
  
  Revealer.prototype.content = function(el) {
    this.el.find(this._csel).empty().append(el);
    el.addClass('active')
    return this;
  };
  
  Revealer.prototype.reveal = function(el, rel) {
    if (this.sliding) {
      var self = this;
      this.once('revealed', function() {
        self.reveal(el, rel)
      });
      return this;
    }
    
    var self = this
      , active = this.el.find('.active')
      , next = el
      , direction = rel == 'next' ? 'left' : 'right';
    
    this.sliding = true;
    this.el.find(this._csel).append(el);
    
    next.addClass(rel)
    next[0].offsetWidth // force reflow
    active.addClass(direction)
    next.addClass(direction)
    
    el.one('webkitTransitionEnd', function() {
      next.removeClass([rel, direction].join(' ')).addClass('active');
      active.removeClass(['active', direction].join(' '));
      active.remove();
      self.sliding = false;
      setTimeout(function () { self.emit('revealed') }, 0);
    });
    
    return this;
  }
  
  return Revealer;
});
