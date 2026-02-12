define(['view',
        'render',
        'class'],
function(View, render, clazz) {
  
  // TODO: Implement support for effects.
  
  function Carousel(el, options) {
    options = options || {};
    Carousel.super_.call(this, el, options);
    this._listEl = this.el.find(options.listSelector || 'ul');
    this._itemSel = options.itemSelector || 'li';
    this._items = [];
    this._i = 0;
    this._scrollBy = options.scrollBy || 1;
    
    var self = this;
    this.el.find('.next').on('click', function() {
      self._scrollto(self._i + self._scrollBy, self._i);
      return false;
    });
    this.el.find('.prev').on('click', function() {
      self._scrollto(self._i - self._scrollBy, self._i);
      return false;
    });
    
    this._listEl.on('click', function(e) {
      var iel = render.$(e.target).closest(self._itemSel);
      self.emit('click', iel, iel.index());
      iel.siblings().removeClass('active');
      iel.addClass('active');
      return false;
    });
  }
  clazz.inherits(Carousel, View);
  
  Carousel.prototype.item = function(el, i) {
    if (i === undefined) {
      this._items.push(el);
      this._listEl.append(el);
    } else {
      this._items.splice(i, 0, el);
      if (i == 0) {
        this._listEl.prepend(el);
      } else {
        this._items[i - 1].after(el);
      }
    }
    return this;
  };
  
  Carousel.prototype.active = function(i) {
    var iel = this._items[i];
    iel.siblings().removeClass('active');
    iel.addClass('active');
  }
  
  Carousel.prototype._scrollto = function(i, pi) {
    if (i < 0 || i >= this._items.length) return;
    
    this._i = i;
    var pos = toFloat(this._listEl.position()['left'])
      , adj = this._adjustment(i, pi);
  
    if (adj === 0) return;
  
    var props = {};
    props['left'] = (pos + adj) + 'px';
  
    // TODO: Animate this transition.
    this._listEl.css(props);
  }
  
  Carousel.prototype._adjustment = function(i, pi) {
    var pitem = this._items[pi]
      , item = this._items[i]
      , ppos   = pitem.position()['left']
      , pos = item.position()['left'];
      
    // TODO: Implement center option.
    
    return ppos - pos;
  }
  
  
  function toFloat(val) {
    return parseFloat(val) || 0;
  };
  
  return Carousel;
});
