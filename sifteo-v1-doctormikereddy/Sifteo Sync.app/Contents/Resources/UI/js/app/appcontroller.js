define(['popover',
        'confirmpopover',
        'controller',
        'siftsystem',
        'notifications',
        'class',
        'render'],
function(Popover, ConfirmPopover, Controller, siftSystem, notifications, clazz, render) {
  var $ = render.$;
  
  function AppController(app) {
    this._app = app;
    this._tip = null;
    this._clickedPurchase = false;
    AppController.super_.call(this);
  }
  clazz.inherits(AppController, Controller);
  
  AppController.prototype.template = 'app';
  AppController.prototype.events = {
    'click .js-install': 'onInstallClicked',
    'click .js-install-demo': 'onInstallDemoClicked',
    'click .js-download': 'onDownloadClicked',
    'click .js-purchase': 'onPurchaseClicked',
    'click .js-purchase-demo': 'onPurchaseDemoClicked'
  }
  
  AppController.prototype.onInstallClicked = function(e) {
    var self = this
      , el = $(e.currentTarget);
    
    if (el.hasClass('disabled')) return;
    
    function open(cb) {
      // TODO: Display activity indicator.
      
      var opener = self._app.open(function(err) {
        if (err) { return cb(err); }
        return cb();
      });
    }
    
    function install(cb) {
      var installer = self._app.install(siftSystem.devices.active, function(err) {
        if (err) {
          //prog.hide();
          return cb(err);
        }
        return cb();
      });
    }
    
    function raise(err) {
      // TODO: Consolidate error codes to a single location.
      if (err.code == 201) {
        if (self._tip) { self._tip.hide(); }
        
        var message = 'Your Sifteo Base needs to be updated before ' + self._app.title + ' can be installed. Update now?';
        
        self._tip = new ConfirmPopover('confirm-popover', { position: 'west', text: message });
        self._tip.on('ok', function() {
          siftSystem.devices.active.promptUpdate();
        })
        self._tip.show(self.el.find('.actions'));
      } else {
        var info = {};
        info.suggestion = "Plug in your Sifteo Base and try again.";
        if (err.code == 202) {
          info.suggestion = "Remove an app from your Sifteo Base and try again.";
        }
        info.error = err;
        notifications.post('unhandledError', null, info);
      }
    }
    
    
    if (!this._app.isOpen) {
      open(function(err) {
        if (err) return raise(err);
        install(function(err) {
          if (err) return raise(err);
        });
      });
    } else {
      install(function(err) {
        if (err) return raise(err);
      });
    }
  }
  
  AppController.prototype.onInstallDemoClicked = function(e) {
    var self = this
      , el = $(e.currentTarget);
      
    if (el.hasClass('disabled')) return;
    
    function install(cb) {
      var installer = self._app.installDemo(siftSystem.devices.active, function(err) {
        if (err) {
          //prog.hide();
          return cb(err);
        }
        return cb();
      });
    }
    
    function raise(err) {
      // TODO: Consolidate error codes to a single location.
      if (err.code == 201) {
        if (self._tip) { self._tip.hide(); }
        
        var message = 'Your Sifteo Base needs to be updated before ' + self._app.title + ' can be installed. Update now?';
        
        self._tip = new ConfirmPopover('confirm-popover', { position: 'west', text: message });
        self._tip.on('ok', function() {
          siftSystem.devices.active.promptUpdate();
        })
        self._tip.show(self.el.find('.actions'));
      } else {
        var info = {};
        info.suggestion = "Plug in your Sifteo Base and try again.";
        if (err.code == 202) {
          info.suggestion = "Remove an app from your Sifteo Base and try again.";
        }
        info.error = err;
        notifications.post('unhandledError', null, info);
      }
    }
    
    install(function(err) {
      if (err) return raise(err);
    });
  }
  
  AppController.prototype.onDownloadClicked = function(e) {
    var self = this
      , el = $(e.currentTarget);
    
    if (el.hasClass('disabled')) return;
    var fetcher = self._app.fetch(function(err) {
      if (err) {
        var info = {};
        info.description = "Failed to download " + self._app.title + ".";
        info.suggestion = "Check your Internet connection and try again.";
        info.error = err;
        notifications.post('unhandledError', null, info);
      }
    });
  }
  
  AppController.prototype.onPurchaseClicked = function(e) {
    var self = this
      , el = $(e.currentTarget)
      , app = this._app;
      
    if (el.hasClass('disabled')) return;
    
    function purchase() {
      self._clickedPurchase = true;
      el.addClass('disabled');
      siftSystem.cloud.post({ price: app.price }, '/apps/' + app.id + '/purchase', function(res) {
        res.on('end', function() {
          el.removeClass('disabled');
          // TODO: Show and hide activity indicator
        });
      }).on('error', function(err) {
        el.removeClass('disabled');
        var info = {};
        info.description = "Failed to buy " + self._app.title + ".";
        info.suggestion = "Check your Internet connection and try again.";
        info.error = err;

        if (err.responseObject) {
          var errRes = err.responseObject;
          if (errRes.message) {
            info.error.message = errRes.message;
          }
          if (errRes.errors && errRes.errors.length) {
            info.error.message = errRes.errors[0].message;
          }
        }

        notifications.post('unhandledError', null, info);
      });
    }
    
    
    var message = 'You will be purchasing ' + this._app.title + ' for ' + this._app.price + ' credits. Are you sure?';
  
    if (this._tip) { this._tip.hide(); }
    this._tip = new ConfirmPopover('confirm-popover', { position: 'west', text: message });
    this._tip.on('ok', function() {
      purchase();
    })
    this._tip.show(this.el.find('.actions'));
    return;
  }
  
  AppController.prototype.onPurchaseDemoClicked = function(e) {
    var self = this
      , el = $(e.currentTarget)
      , app = this._app;
      
    if (el.hasClass('disabled')) return;
    
    function purchase() {
      self._clickedPurchase = true;
      el.addClass('disabled');
      siftSystem.cloud.get('/apps/' + app.id + '/demo', function(res) {
        res.on('end', function() {
          //el.removeClass('disabled');
          // TODO: Show and hide activity indicator
        });
      });
    }
    
    if (app.isDemoClaimed) {
      app.fetch();
    } else {
      purchase();
    }
    return;
  }
  
  AppController.prototype.willLoadDib = function() {
    return this._app;
  }
  
  AppController.prototype.didLoadDib = function() {
    console.log('AppController.didLoadDib');
    console.log('  id: ' + this._app.id);
    console.log('  hasDemo: ' + this._app.hasDemo);
    
    if (this._app.isSellable) {
      if (!this._app.hasDemo) {
        this.el.find('.app-actions-normal').addClass('is-sellable');
      } else {
        this.el.find('.app-actions-normal').hide();
        this.el.find('.app-actions-demoable').show();
        
        if (this._app.isDemoLocal) {
          this.el.find('.app-actions-demoable').addClass('is-demo-local');
        } else {
          this.el.find('.app-actions-demoable').addClass('is-demo-claimable');
        }
      }
  
      if (!siftSystem.user) {
        this.el.find('.js-purchase').hide();
      }
    } else if (this._app.isCubeEnhanced) {
      if (this._app.isLocal) {
        this.el.find('.app-actions-normal').addClass('is-local');
      } else {
        this.el.find('.app-actions-normal').addClass('is-remote');
      }
    } else {
      this.el.find('.actions').hide();
    }
    
    notifications.on('deviceSelected', function(notif) {
      var dev = notif.info.device;
      dev.on('appsChanged', function() {
        updateDeviceState(dev);
      });
      updateDeviceState(dev);
    });
    
    notifications.on('deviceDeselected', function(notif) {
      updateDeviceState();
    });
    
    var self = this;
    function updateDeviceState(dev) {
      if (dev) {
        // TODO: Update with demo checks
        
        if (self._app.isInstalled(dev)) {
          self.el.find('.js-install .inner').html('<span class="text">Game Installed</span>');
          self.el.find('.js-install').addClass('disabled')
        } else {
          self.el.find('.js-install .inner').html('<img src="img/en/install-game.png" width="90" height="9"/>')
          self.el.find('.js-install').removeClass('disabled')
        }
        
        if (self._app.isDemoInstalled(dev)) {
          self.el.find('.js-install-demo .inner').html('<span class="text">Demo Installed</span>');
          self.el.find('.js-install-demo').addClass('disabled')
        } else {
          self.el.find('.js-install-demo .inner').html('<img src="img/en/install-demo.png" width="91" height="9"/>')
          self.el.find('.js-install-demo').removeClass('disabled')
        }
      } else {
        self.el.find('.js-install .inner').html('<img src="img/en/install-game.png" width="90" height="9"/>')
        self.el.find('.js-install').addClass('disabled')
        
        self.el.find('.js-install-demo .inner').html('<img src="img/en/install-demo.png" width="91" height="9"/>')
        self.el.find('.js-install-demo').addClass('disabled')
      }
    }
    
    updateDeviceState(siftSystem.devices.active);
    if (siftSystem.devices.active) {
      siftSystem.devices.active.on('appsChanged', function() {
        updateDeviceState(siftSystem.devices.active);
      });
    }
    
    
    // TODO: Replace this with a better "missing booklet" template
    if (this._app.bookletURL.length == 0) {
      this.el.find('.title').show();
    }
    
    
    // TODO: For patterns that can make this type of code more succinct, see
    //       https://github.com/visionmedia/node-pause/blob/master/index.js
    this._onpropertychanged = onPropertyChanged.bind(this);
    this._ondownloadstart = onDownloadStart.bind(this);
    this._ondownloadend = onDownloadEnd.bind(this);
    this._ondownloaderror = onDownloadError.bind(this);
    this._oninstallstart = onInstallStart.bind(this);
    this._oninstallend = onInstallEnd.bind(this);
    this._oninstallerror = onInstallError.bind(this);
    this._app.on('propertyChanged', this._onpropertychanged);
    this._app.on('downloadStart', this._ondownloadstart);
    this._app.on('downloadEnd', this._ondownloadend);
    this._app.on('downloadError', this._ondownloaderror);
    this._app.on('installStart', this._oninstallstart);
    this._app.on('installEnd', this._oninstallend);
    this._app.on('installError', this._oninstallerror);
  }
  
  AppController.prototype.willRemoveEl = function() {
    if (this._tip) { this._tip.hide(); }
    
    this._app.off('propertyChanged', this._onpropertychanged);
    this._app.off('downloadStart', this._ondownloadstart);
    this._app.off('downloadEnd', this._ondownloadend);
    this._app.off('downloadError', this._ondownloaderror);
    this._app.off('installStart', this._oninstallstart);
    this._app.off('installEnd', this._oninstallend);
    this._app.off('installError', this._oninstallerror);
  }
  
  
  function onPropertyChanged(key, val) {
    if (key == 'isRemote' || key == 'isDemoRemote' || key == 'isSellable') {
      if (this._app.isSellable) {
        if (!this._app.hasDemo) {
          this.el.find('.app-actions-demoable').hide();
          this.el.find('.app-actions-normal').show();
          
          this.el.find('.app-actions-normal').removeClass('is-remote');
          this.el.find('.app-actions-normal').removeClass('is-local');
          this.el.find('.app-actions-normal').addClass('is-sellable');
          
        } else {
          this.el.find('.app-actions-normal').hide();
          this.el.find('.app-actions-demoable').show();
        
          if (this._app.isDemoLocal) {
            this.el.find('.app-actions-demoable').removeClass('is-demo-claimable');
            this.el.find('.app-actions-demoable').removeClass('is-demo-remote');
            this.el.find('.app-actions-demoable').addClass('is-demo-local');
          } else {
            this.el.find('.app-actions-demoable').removeClass('is-demo-local');
            this.el.find('.app-actions-demoable').removeClass('is-demo-remote');
            this.el.find('.app-actions-demoable').addClass('is-demo-claimable');
          }
        }
      } else if (this._app.isCubeEnhanced) {
        this.el.find('.app-actions-demoable').hide();
        this.el.find('.app-actions-normal').show();
        
        if (this._app.isLocal) {
          this.el.find('.app-actions-normal').removeClass('is-remote');
          this.el.find('.app-actions-normal').removeClass('is-sellable');
          this.el.find('.app-actions-normal').addClass('is-local');
        } else {
          this.el.find('.app-actions-normal').removeClass('is-local');
          this.el.find('.app-actions-normal').removeClass('is-sellable');
          this.el.find('.app-actions-normal').addClass('is-remote');
        }
      } else {
        this.el.find('.actions').hide();
      }
    }
  }
  
  
  function onDownloadStart() {
    this.el.find('.js-download').addClass('disabled');
    this.el.find('.js-download .inner').html('<span class="text">Downloading</span>');
    
    this.el.find('.js-purchase-demo').addClass('disabled');
    this.el.find('.js-purchase-demo .inner').html('<span class="text">Downloading</span>');
  }
  
  function onDownloadEnd() {
    this.el.find('.js-download').removeClass('disabled');
    this.el.find('.js-purchase-demo').removeClass('disabled');
    
    if (this._clickedPurchase) {
      var message = this._app.title + ' has been downloaded. Plug your Sifteo Base into your computer with a USB cable to install.';
      if (siftSystem.devices.active) {
        message = this._app.title + ' has been downloaded to your computer and is ready to install. Click Install to put it on your Sifteo Base.';
      }
    
      if (this._tip) { this._tip.hide(); }
      this._tip = new Popover('coach-popover', { text: message });
      this._tip.show(this.el.find('.actions'));
    }
  }
  
  function onDownloadError(err) {
    this.el.find('.js-download').removeClass('disabled');
  }
  
  function onInstallStart() {
    this.el.find('.js-install').addClass('disabled');
    this.el.find('.js-install .inner').html('<span class="text">Installing</span>');
    
    this.el.find('.js-install-demo').addClass('disabled');
    this.el.find('.js-install-demo .inner').html('<span class="text">Installing</span>');
  }
  
  function onInstallEnd() {
    this.el.find('.js-install').removeClass('disabled');
    this.el.find('.js-install-demo').removeClass('disabled');
    
    var message = this._app.title + ' has been installed onto your Sifteo Base. You can unplug your base and play it now!';
    if (this._tip) { this._tip.hide(); }
    this._tip = new Popover('coach-popover', { text: message });
    this._tip.show(this.el.find('.actions'));
  }
  
  function onInstallError() {
    this.el.find('.js-install .inner').html('<img src="img/en/install-game.png" width="90" height="9"/>');
    this.el.find('.js-install').removeClass('disabled');
    
    this.el.find('.js-install-demo .inner').html('<img src="img/en/install-demo.png" width="91" height="9"/>')
    this.el.find('.js-install-demo').addClass('disabled')
  }

  return AppController;
});
