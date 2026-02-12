define(['./logincontroller',
        './registercontroller',
        './accountcontroller',
        './basedevicecontroller',
        './shopcontroller',
        './redeemcodecontroller',
        'popover',
        'controller',
        'siftsystem',
        'notifications',
        'class'],
function(LogInController, RegisterController, AccountController, BaseDeviceController, ShopController, RedeemCodeController, Popover, Controller, siftSystem, notifications, clazz) {
  var settings = siftSystem.settings;
  
  function MenuController() {
    MenuController.super_.call(this);
    this._logInTip = null;
  }
  clazz.inherits(MenuController, Controller);
  
  MenuController.prototype.template = 'menu';
  MenuController.prototype.events = {
    'click .brand': 'onBrandClicked',
    'click a[href="#login"]': 'onLogInClicked',
    'click a[href="#logout"]': 'onLogOutClicked',
    'click a[href="#account"]': 'onAccountClicked',
    'click a[href="#device"]': 'onDeviceClicked',
    'click a[href="#shop"]': 'onShopClicked',
    'click a[href="#redeem-code"]': 'onRedeemCodeClicked'
  }
  
  MenuController.prototype.onBrandClicked = function(e) {
    siftSystem.services.open('http://www.sifteo.com/')
    return false;
  }
  
  MenuController.prototype.onLogInClicked = function(e) {
    if (this._logInTip) { this._logInTip.hide(); }
    
    var vc = new LogInController();
    vc.on('register', function() {
      var vc = new RegisterController();
      vc.present();
    });
    vc.present();
    return false;
  }
  
  MenuController.prototype.onLogOutClicked = function(e) {
    siftSystem.logOut();
    return false;
  }
  
  MenuController.prototype.onAccountClicked = function(e) {
    var vc = new AccountController(siftSystem.user, { present: 'popover' });
    vc.on('logout', function() {
      siftSystem.logOut();
    });
    vc.present(e.currentTarget);
    return true;
  }
  
  MenuController.prototype.onDeviceClicked = function(e) {
    if (!siftSystem.devices.active) return;
    var vc = new BaseDeviceController(siftSystem.devices.active, { present: 'popover' });
    vc.present(e.currentTarget);
    return false;
  }
  
  MenuController.prototype.onShopClicked = function(e) {
    if (!siftSystem.user) {
      var vc = new LogInController();
      vc.on('register', function() {
        var vc = new RegisterController();
        vc.present();
      });
      vc.present('purchase-credits');
      return;
    }
    
    if (!this._shopCtrl) {
      this._shopCtrl = new ShopController({ present: 'popover' });
      var self = this;
      this._shopCtrl.on('done', function() {
        self._shopCtrl = null;
      });
    }
    
    this._shopCtrl.present(e.currentTarget);
    return false;
  }
  
  MenuController.prototype.onRedeemCodeClicked = function(e) {
    if (!siftSystem.user) {
      var vc = new LogInController();
      vc.on('register', function() {
        var vc = new RegisterController();
        vc.present();
      });
      vc.present('redeem-code');
      return;
    }
    
    if (!this._redeemCodeCtrl) {
      this._redeemCodeCtrl = new RedeemCodeController({ present: 'popover' });
      var self = this;
      this._redeemCodeCtrl.on('done', function() {
        self._redeemCodeCtrl = null;
      });
    }
    
    this._redeemCodeCtrl.present(e.currentTarget);
    return false;
  }
  
  MenuController.prototype.didLoadDib = function() {
    var self = this;
    
    if (siftSystem.user) {
      this.el.find('#mb-login').hide();
      this.el.find('#mb-account .username').text(siftSystem.user.email)
      this.el.find('#mb-shop .credits .amount').text(siftSystem.user.balance)
      
      siftSystem.user.on('propertyChanged', function(prop, val) {
        if (prop == 'balance') {
          self.el.find('#mb-shop .credits .amount').text(val)
        }
      });
    } else {
      this.el.find('#mb-account').hide();
      //this.el.find('#mb-shop').hide();
      this.el.find('#mb-login').show();
      
      if (settings.get('coachLogIn', true)) {
        var self = this;
        setTimeout(function() {
          self._logInTip = new Popover('coach-popover', { text: 'Welcome! Log in to redeem codes, buy credits and download games!' });
          self._logInTip.show(self.el.find('#mb-login'));
          self._logInTip.on('hide', function() {
            settings.set('coachLogIn', false);
          });
        }, 10);
      }
    }
    
    if (siftSystem.devices.active) {
      this.el.find('a[href="#device"]').removeClass('disconnected');
      this.el.find('a[href="#device"]').addClass('connected');
      
      var dev = siftSystem.devices.active;
      if (dev.isReady) {
        notifications.post('deviceSelected', null, { device: dev });
      } else {
        dev.once('ready', function() {
          notifications.post('deviceSelected', null, { device: dev });
        });
      }
    } else {
      notifications.post('deviceDeselected', null);
    }
    
    
    siftSystem.on('login', function() {
      self.el.find('#mb-login').hide();
      self.el.find('#mb-account').show();
      self.el.find('#mb-shop').show();
      
      self.el.find('#mb-account .username').text(siftSystem.user.email)
      self.el.find('#mb-shop .credits .amount').text(siftSystem.user.balance)
      
      siftSystem.user.on('propertyChanged', function(prop, val) {
        if (prop == 'balance') {
          self.el.find('#mb-shop .credits .amount').text(val)
        }
      });
    });
    
    siftSystem.on('logout', function() {
      self.el.find('#mb-account').hide();
      //self.el.find('#mb-shop').hide();
      self.el.find('#mb-login').show();
      
      self.el.find('#mb-shop .credits .amount').text(0)
    });
    
    siftSystem.devices.on('detected', function(dev) {
      self.el.find('a[href="#device"]').removeClass('disconnected');
      self.el.find('a[href="#device"]').addClass('connected');
      
      if (dev.isReady) {
        notifications.post('deviceSelected', null, { device: dev });
      } else {
        dev.once('ready', function() {
          notifications.post('deviceSelected', null, { device: dev });
        });
      }
      
      dev.once('error', function(err) {
        var info = {};
        info.description = "Oh no. We're having trouble talking to your Sifteo Base.";
        info.suggestion = "Reconnect your Sifteo Base and try again.";
        info.error = err;
      
        notifications.post('unhandledError', null, info);
      })
    });
    
    siftSystem.devices.on('undetected', function() {
      self.el.find('a[href="#device"]').removeClass('connected');
      self.el.find('a[href="#device"]').addClass('disconnected');
      
      notifications.post('deviceDeselected', null);
    });
  }
  
  return MenuController;
});
