define(['./appcontroller',
        './appiconcontroller',
        './ui/revealer',
        './ui/launcher',
        'carousel',
        'dib',
        'controller',
        'siftsystem',
        'class'],
function(AppController, AppIconController, Revealer, Launcher, Carousel, Dib, Controller, siftSystem, clazz) {
  
  function LibraryController() {
    this._appCtrl = null;
    // Keep separate apps array, since order isn't aligned with the underlying
    // siftSystem order (promos are prepended)
    this._apps = [];
    this._i = 0;
    this._promoIdx = 0;
    LibraryController.super_.call(this);
  }
  clazz.inherits(LibraryController, Controller);
  
  LibraryController.prototype.template = 'library';
  
  LibraryController.prototype.onLauncherClick = function(el, i) {
    if (i == this._i) return;
    this._open(i, this._i);
  }
  
  LibraryController.prototype.onRevealRight = function() {
    if (this._i == this._apps.length - 1) { return; }
    this._open(this._i + 1, this._i);
    this._carousel.active(this._i);
  }
  
  LibraryController.prototype.onRevealLeft = function() {
    if (this._i == 0) return;
    this._open(this._i - 1, this._i);
    this._carousel.active(this._i);
  }
  
  LibraryController.prototype.onRevealerRevealed = function() {
    if (this._i == 0) {
      this.el.find('.app-carousel .left').addClass('hide');
      this.el.find('.app-carousel .right').removeClass('hide');
    } else if (this._i == siftSystem.apps.length - 1) {
      this.el.find('.app-carousel .left').removeClass('hide');
      this.el.find('.app-carousel .right').addClass('hide');
    } else {
      this.el.find('.app-carousel .left').removeClass('hide');
      this.el.find('.app-carousel .right').removeClass('hide');
    }
  }
  
  LibraryController.prototype.didLoadDib = function() {
    var revealer = this._revealer = new Revealer(this.el.find('.carousel'), { contentSelector: '.carousel-inner' });
    revealer.on('next', this.onRevealRight.bind(this))
            .on('prev', this.onRevealLeft.bind(this))
            .on('revealed', this.onRevealerRevealed.bind(this));
    
    var carousel = this._carousel = new Carousel(this.el.find('.launcher'), { listSelector: '.items', itemSelector: '.item', scrollBy: 5 });
    carousel.on('click', this.onLauncherClick.bind(this));
    
    for (var i = 0, len = siftSystem.apps.length; i < len; i++) {
      var app = siftSystem.apps.at(i);
      this._apps.push(app);
      var ictl = new AppIconController(app);
      this._carousel.item(ictl.el);
      if (i == 0) {
        this._appCtrl = new AppController(app);
        this._revealer.content(this._appCtrl.el);
        this._carousel.active(0);
        this.el.find('.app-carousel .left').addClass('hide');
      }
    }
    
    this._onadded = onAdded.bind(this);
    siftSystem.apps.on('added', this._onadded);
  }
  
  LibraryController.prototype.destroy = function() {
    if (this._onadded) { siftSystem.apps.off('added', this._onadded); this._onadded = null; }
    
    // FIXME: If the element is removed from the DOM, a crash condition is
    //        encountered when the next onadded or onfeatured signal is emitted.
    //        This appears to be a bug in Qt (specifically the QtWebKit bridge),
    //        and is filed in Bugzilla here:
    //
    //          https://bugs.webkit.org/show_bug.cgi?id=82383
    //
    //        As a workaround, instead of removing the element from the DOM, it
    //        is simply hidden.  As a consequence, the DOM will accumulate cruft
    //        if many successive login/logout actions are taken.  Under normal
    //        operation, this doesn't pose a serious problem, but it should be
    //        revisited and fixed at some point in the future.
    this.el.remove();
    //this.el.hide();
  }
  
  LibraryController.prototype._open = function(i, pi) {
    if (this._appCtrl) { this._appCtrl.willRemoveEl(); }
    this._i = i;
    var app = this._apps[i];
    this._appCtrl = new AppController(app);
    var rel = (i > pi) ? 'next' : 'prev';
    this._revealer.reveal(this._appCtrl.el, rel);
  }
  
  
  function onAdded(app) {
    var idx = undefined;
    if (app.isPromoted) {
      idx = this._promoIdx;
      this._promoIdx += 1;
    }
    
    if (idx === undefined) {
      this._apps.push(app);
    } else {
      this._apps.splice(idx, 0, app);
      if (idx <= this._i) this._i++;
    }
  
    var ictl = new AppIconController(app);
    this._carousel.item(ictl.el, idx);
    if (siftSystem.apps.length == 1) {
      this._appCtrl = new AppController(app);
      this._revealer.content(this._appCtrl.el);
      this._carousel.active(0);
    }
  }

  return LibraryController;
});
