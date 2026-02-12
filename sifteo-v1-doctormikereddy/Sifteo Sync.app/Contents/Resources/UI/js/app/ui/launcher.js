define(['view',
        'render',
        'class'],
function(View, render, clazz) {
  
  function Launcher(el, options) {
    Launcher.super_.call(this, el, options);
    options = options || {};
    this._bodysel = options.bodySelector || options.contentSelector || '.body';
    this._isel = options.itemSelector || '.item';
    this._per = options.per || 5;
    
    var self = this
      , el = this.el;
      
    el.find(this._bodysel).on('click', function(e) {
      var iel = render.$(e.target).closest(self._isel)
        , pel = iel.parent()
        , page = pel.parent().children().index(pel);
      
      var i = parseInt((page * self._per) + iel.index());
      self.emit('click', iel, i);
      iel.siblings().removeClass('active');
      iel.addClass('active');
      return false;
    });
    
    el.find('.prev').on('click', function() {
      var active = self.el.find('.page.active')
        , children = active.parent().children()
        , i = children.index(active);
      
      self.page(i - 1);
      return false;
    });
    el.find('.next').on('click', function() {
      var active = self.el.find('.page.active')
        , children = active.parent().children()
        , i = children.index(active);
      
      self.page(i + 1);
      return false;
    });
  }
  clazz.inherits(Launcher, View);
  
  Launcher.prototype.item = function(el) {
    var page = this.el.find('.page').last()
      , items = page.children().length;
    
    if (items < this._per) {
      page.append(el);
    } else {
      var np = render.$('<div class="page"></div>');
      np.append(el);
      this.el.find('.body').append(np);
    }
    return this;
  };
  
  Launcher.prototype.active = function(i) {
    var p = Math.floor(i / this._per);
    var m = i % this._per;
  
    var pel = render.$(this.el.find('.page')[p]);
    var iel = render.$(pel.find('.item')[m]);
    
    this.page(p);
    this.el.find('.item').removeClass('active');
    iel.addClass('active');
  }
  
  Launcher.prototype.page = function(i) {
    var active = this.el.find('.page.active')
      , children = active.parent().children();
    
    if (i > (children.length - 1) || i < 0) return
    
    active.removeClass('active');
    render.$(children[i]).addClass('active');
  }
  
  return Launcher;
});
