define(['controller',
        'class'],
function(Controller, clazz) {
  
  function AppIconController(app) {
    this._app = app;
    AppIconController.super_.call(this);
  }
  clazz.inherits(AppIconController, Controller);
  
  AppIconController.prototype.template = 'app-icon';
  
  AppIconController.prototype.willLoadDib = function() {
    return {
      iconURL: this._app.iconURL || 'img/launcher-icon-not-found.png'
    };
  }
  
  AppIconController.prototype.didLoadDib = function() {
    this._progEl = this.el.find('.progress').first();
    this._progBarEl = this.el.find('.progress .bar').first();
    
    if (this._app.ribbonURL) {
      this.el.find('.ribbon').html('<img src="' + this._app.ribbonURL + '"/>');
    } else {
      this.el.find('.ribbon').html('');
    }
    
    this._onpropertychanged = onPropertyChanged.bind(this);
    this._ondownloadprogress = onDownloadProgress.bind(this);
    this._ondownloadend = onDownloadEnd.bind(this);
    this._ondownloaderror = onDownloadError.bind(this);
    this._oninstallprogress = onInstallProgress.bind(this);
    this._oninstallend = onInstallEnd.bind(this);
    this._oninstallerror = onInstallError.bind(this);
    this._app.on('propertyChanged', this._onpropertychanged);
    this._app.on('downloadProgress', this._ondownloadprogress);
    this._app.on('downloadEnd', this._ondownloadend);
    this._app.on('downloadError', this._ondownloaderror);
    this._app.on('installProgress', this._oninstallprogress);
    this._app.on('installEnd', this._oninstallend);
    this._app.on('installError', this._oninstallerror);
  }
  
  
  function onPropertyChanged(key, val) {
    switch (key) {
      case 'iconURL':
        this.el.find('img').attr('src', val)
        break;
      case 'isSellable':
        if (!val) {
          // TODO: Watch for ribbon URL changes
          this.el.find('.ribbon').html('');
        }
        break;
    }
  }
  
  function onDownloadProgress(partial, total) {
    var pct = Math.round((partial / total) * 100);
    if (pct !== this._prog) {
      this._progEl.show();
      this._progBarEl.width(pct + '%');
      this._prog = pct;
    }
  }
  
  function onDownloadEnd() {
    this._progEl.hide();
  }
  
  function onDownloadError(err) {
    this._progEl.hide();
  }
  
  function onInstallProgress(partial, total) {
    var pct = Math.round((partial / total) * 100);
    if (pct !== this._prog) {
      this._progEl.show();
      this._progBarEl.width(pct + '%');
      this._prog = pct;
    }
  }
  
  function onInstallEnd() {
    this._progEl.hide();
  }
  
  function onInstallError(err) {
    this._progEl.hide();
  }
  
  // TODO: Implement a way to set an ID based on the underlying app object.
  //       Not needed until we need to remove elements.
  /*
  dib.container({
    'tag': 'div', 'attrs': { 'class': 'selector-item', 'id': 'selector-id-' + app.id.replace(/\./g, '_') }
  })
  */
  
  return AppIconController;
});
