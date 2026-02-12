define(['dialog',
        'controller',
        'siftsystem',
        'class'],
function(Dialog, Controller, siftSystem, clazz) {
  
  function LogInController() {
    LogInController.super_.call(this);
  }
  clazz.inherits(LogInController, Controller);
  
  LogInController.prototype.template = 'login';
  LogInController.prototype.events = {
    'submit': 'onLogIn',
    'click a[href$="#register"]': 'onRegister'
  }
  
  LogInController.prototype.present = function(reason) {
    switch (reason) {
      case 'purchase-credits':
        this.el.find('.help-text').text('To buy more credits, please log in or create an account.');
        this.el.find('.tip').removeClass('hide');
        break;
      case 'redeem-code':
        this.el.find('.help-text').text('To redeem a code, please log in or create an account.');
        this.el.find('.tip').removeClass('hide');
        break;
      default:
    }
    
    this._dialog.show();
  }
  
  LogInController.prototype.onLogIn = function(e) {
    var username = this.el.find('input[name="username"]').val();
    var password = this.el.find('input[name="password"]').val();
    
    // ensure username and password are not empty
    var el = this.el
        , verrs = [];

    if (username.length < 1) {
      verrs.push({ selector: 'input[name="username"]' });
    }

    if (password.length < 1) {
      verrs.push({ selector: 'input[name="password"]' });
    }

    el.find('input').removeClass('error');

    if (verrs.length) {
      for (var i = 0, len = verrs.length; i < len; i++) {
        var verr = verrs[i];
        el.find(verr.selector).addClass('error');
      }
      return false;
    }

    var self = this;
    siftSystem.logIn(username, password, function(err) {
      if (err) {
        var msg = err.message || 'Failed to log in.';
        self.el.find('p.dlg-status').html(msg);
        self.el.find('p.dlg-status').addClass('error');
        return;
      }
      self._dialog.hide();
    })
    this.el.find('p.dlg-status').html('Logging in...');
    return false;
  }
  
  LogInController.prototype.onRegister = function(e) {
    //siftSystem.services.open('http://www.sifteo.com/register')
    
    // timeout needed to work around QtWebKit bug
    var self = this;
    setTimeout(function() {
      self._dialog.hide();
      self.emit('register');
    }, 10);
    return false;
  }
  
  LogInController.prototype.didLoadDib = function() {
    this._dialog = new Dialog(this.el);
    this._dialog.overlay({closable: true});
  }

  return LogInController;
});
