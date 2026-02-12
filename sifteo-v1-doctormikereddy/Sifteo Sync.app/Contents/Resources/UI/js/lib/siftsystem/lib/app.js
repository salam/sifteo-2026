define(['./fetcher',
        './installer',
        './opener',
        './errors/fetcherror',
        './errors/installerror',
        './errors/openerror',
        'events',
        'class'],
function(Fetcher, Installer, Opener, FetchError, InstallError, OpenError, Emitter, clazz) {
  
  function App(obj) {
    App.super_.call(this);
    this._qtApp = obj;
    this.init();
  }
  clazz.inherits(App, Emitter);
  
  App.prototype.init = function() {
    var self = this;
    
    this.__defineGetter__('id', function() {
      return self._qtApp.id;
    });
    this.__defineGetter__('version', function() {
      return self._qtApp.version;
    });
    this.__defineGetter__('title', function() {
      return self._qtApp.title;
    });
    this.__defineGetter__('iconURL', function() {
      return self._qtApp.iconURL;
    });
    this.__defineGetter__('bookletURL', function() {
      return self._qtApp.bookletURL;
    });
    this.__defineGetter__('ribbonURL', function() {
      return self._qtApp.ribbonURL;
    });
    this.__defineGetter__('price', function() {
      return self._qtApp.price;
    });
    this.__defineGetter__('hasDemo', function() {
      return self._qtApp.hasDemo;
    });
    this.__defineGetter__('isOpen', function() {
      return self._qtApp.isOpen;
    });
    this.__defineGetter__('isLocal', function() {
      return self._qtApp.isLocal;
    });
    this.__defineGetter__('isRemote', function() {
      return self._qtApp.isRemote;
    });
    this.__defineGetter__('isDemoLocal', function() {
      return self._qtApp.isDemoLocal;
    });
    this.__defineGetter__('isDemoRemote', function() {
      return self._qtApp.isDemoRemote;
    });
    this.__defineGetter__('isDemoClaimed', function() {
      return self._qtApp.isDemoClaimed;
    });
    this.__defineGetter__('isCubeEnhanced', function() {
      return self._qtApp.isCubeEnhanced;
    });
    this.__defineGetter__('isSellable', function() {
      return self._qtApp.isSellable;
    });
    this.__defineGetter__('isPromoted', function() {
      return self._qtApp.isPromoted;
    });
    
    this._onpropertychanged = onPropertyChanged.bind(this);
    this._ondownloadstart = onDownloadStart.bind(this);
    this._ondownloadprogress = onDownloadProgress.bind(this);
    this._ondownloaddone = onDownloadDone.bind(this);
    this._ondownloaderror = onDownloadError.bind(this);
    this._oninstallstart = onInstallStart.bind(this);
    this._oninstallprogress = onInstallProgress.bind(this);
    this._oninstalldone = onInstallDone.bind(this);
    this._oninstallerror = onInstallError.bind(this);
    this._qtApp.onpropertychanged.connect(this._onpropertychanged);
    this._qtApp.ondownloadstart.connect(this._ondownloadstart);
    this._qtApp.ondownloadprogress.connect(this._ondownloadprogress);
    this._qtApp.ondownloaddone.connect(this._ondownloaddone);
    this._qtApp.ondownloaderror.connect(this._ondownloaderror);
    this._qtApp.oninstallstart.connect(this._oninstallstart);
    this._qtApp.oninstallprogress.connect(this._oninstallprogress);
    this._qtApp.oninstalldone.connect(this._oninstalldone);
    this._qtApp.oninstallerror.connect(this._oninstallerror);
  }
  
  App.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._onpropertychanged) { this._qtApp.onpropertychanged.disconnect(this._onpropertychanged); this._onpropertychanged = null; }
    if (this._ondownloadstart) { this._qtApp.ondownloadstart.disconnect(this._ondownloadstart); this._ondownloadstart = null; }
    if (this._ondownloadprogress) { this._qtApp.ondownloadprogress.disconnect(this._ondownloadprogress); this._ondownloadprogress = null; }
    if (this._ondownloaddone) { this._qtApp.ondownloaddone.disconnect(this._ondownloaddone); this._ondownloaddone = null; }
    if (this._ondownloaderror) { this._qtApp.ondownloaderror.disconnect(this._ondownloaderror); this._ondownloaderror = null; }
    if (this._oninstallstart) { this._qtApp.oninstallstart.disconnect(this._oninstallstart); this._oninstallstart = null; }
    if (this._oninstallprogress) { this._qtApp.oninstallprogress.disconnect(this._oninstallprogress); this._oninstallprogress = null; }
    if (this._oninstalldone) { this._qtApp.oninstalldone.disconnect(this._oninstalldone); this._oninstalldone = null; }
    if (this._oninstallerror) { this._qtApp.oninstallerror.disconnect(this._oninstallerror); this._oninstallerror = null; }
    
    this._qtApp = null;
  }
  
  App.prototype.download =
  App.prototype.fetch = function(cb) {
    cb = cb || function() {};
    
    var qtfetcher = this._qtApp.download();
    
    var fetcher = new Fetcher(qtfetcher);
    fetcher.on('end', function() {
      return cb();
    });
    fetcher.on('error', function(err) {
      return cb(err);
    });
    fetcher.start();
    return fetcher;
  }
  
  App.prototype.install = function(dev, cb) {
    cb = cb || function() {};
    
    var qtinstaller = this._qtApp.install(dev._qtDevice);
    if (!qtinstaller) return cb(new InstallError('Incompatible device'));
    
    var installer = new Installer(qtinstaller);
    installer.on('end', function() {
      return cb();
    });
    installer.on('error', function(err) {
      return cb(err);
    });
    installer.start();
    return installer;
  }
  
  App.prototype.installDemo = function(dev, cb) {
    cb = cb || function() {};
    
    var qtinstaller = this._qtApp.installDemo(dev._qtDevice);
    if (!qtinstaller) return cb(new InstallError('Incompatible device'));
    
    var installer = new Installer(qtinstaller);
    installer.on('end', function() {
      return cb();
    });
    installer.on('error', function(err) {
      return cb(err);
    });
    installer.start();
    return installer;
  }
  
  App.prototype.open = function(cb) {
    cb = cb || function() {};
    
    var qtopener = this._qtApp.open();
    if (!qtopener) return cb(new OpenError('Unsupported format'));
    
    var opener = new Opener(qtopener);
    opener.on('end', function() {
      return cb();
    });
    opener.on('error', function(err) {
      return cb(err);
    });
    opener.start();
    return opener;
  }
  
  App.prototype.isInstalled = function(dev) {
    try {
      return this._qtApp.isInstalled(dev._qtDevice);
    } catch(e) {
      // FIXME: This check is needed because AppController isn't removing its listeners
      //        and the app instance is invalidated during login/logout, and old controllers
      //        events are firing.
      return false;
    }
  }
  
  App.prototype.isDemoInstalled = function(dev) {
    try {
      return this._qtApp.isDemoInstalled(dev._qtDevice);
    } catch(e) {
      // FIXME: This check is needed because AppController isn't removing its listeners
      //        and the app instance is invalidated during login/logout, and old controllers
      //        events are firing.
      return false;
    }
  }
  
  
  function onPropertyChanged(prop, val, oldVal) {
    this.emit('propertyChanged', prop, val, oldVal);
  }
  
  function onDownloadStart() {
    this.emit('downloadStart');
  }
  
  function onDownloadProgress(partial, total) {
    this.emit('downloadProgress', partial, total);
  }
  
  function onDownloadDone() {
    this.emit('downloadEnd');
  }
  
  function onDownloadError(code, message) {
    this.emit('downloadError', new FetchError(message, code));
  }
  
  function onInstallStart() {
    this.emit('installStart');
  }
  
  function onInstallProgress(partial, total) {
    this.emit('installProgress', partial, total);
  }
  
  function onInstallDone() {
    this.emit('installEnd');
  }
  
  function onInstallError(code, message) {
    this.emit('installError', new InstallError(message, code));
  }
  
  return App;
});
