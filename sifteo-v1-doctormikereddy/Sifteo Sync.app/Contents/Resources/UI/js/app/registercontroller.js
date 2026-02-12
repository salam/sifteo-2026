define(['dialog',
        'controller',
        'siftsystem',
        'class'],
function(Dialog, Controller, siftSystem, clazz) {
  
  function RegisterController() {
    RegisterController.super_.call(this);
  }
  clazz.inherits(RegisterController, Controller);
  
  RegisterController.prototype.template = 'register-dlg';
  RegisterController.prototype.events = {
    'submit': 'onSubmit'
  }
  
  RegisterController.prototype.present = function() {
    this._dialog.show();
  }
  
  RegisterController.prototype.onSubmit = function(e) {
    if (this._submitted) return false;
    
    var el = this.el
      , verrs = [];
    var givenName = el.find('input[name="name[given_name]"]').val()
      , familyName = el.find('input[name="name[family_name]"]').val()
      , email = el.find('input[name="email"]').val()
      , password = el.find('input[name="password"]').val()
      , passwordConfirmation = el.find('input[name="password_confirmation"]').val()
      , birthYear = el.find('select[name="birthday[year]"] option:selected').val();
    
    if (!givenName.length) {
      verrs.push({ selector: 'input[name="name[given_name]"]' });
    }
    if (!familyName.length) {
      verrs.push({ selector: 'input[name="name[family_name]"]' });
    }
    if (!email.length) {
      verrs.push({ selector: 'input[name="email"]' });
    }
    if (password !== passwordConfirmation || !password.length) {
      verrs.push({ selector: 'input[name="password"]' });
      verrs.push({ selector: 'input[name="password_confirmation"]' });
    }
    
    el.find('.control-group').removeClass('error');
    
    if (verrs.length) {
      for (var i = 0, len = verrs.length; i < len; i++) {
        var verr = verrs[i];
        el.find(verr.selector).closest(verr.container || '.control-group').addClass('error');
      }
      return false;
    }
    
    var user = {};
    user.givenName = givenName;
    user.familyName = familyName;
    user.email = email;
    user.password = password;
    user.birthday = birthYear + '-01-01';
    
    this._submitted = true;
    var self = this;
    siftSystem.cloud.post(user, '/users', function(res) {
      res.on('end', function() {
        siftSystem.logIn(user.email, user.password, function(err) {
          if (err) {
            var msg = err.message || 'Failed to log in.';
            self.el.find('p.dlg-status').html(msg);
            self.el.find('p.dlg-status').addClass('error');
            return;
          }
          self._dialog.hide();
        });
        self.el.find('p.dlg-status').html('Logging in...');
      });
    }).on('error', function(err) {
      self._submitted = false;
      var msg = err.message || 'Failed to create account.';
      if (err.responseObject) {
        var errRes = err.responseObject;
        if (errRes.message) {
          msg = errRes.message;
        }
        for (var prop in errRes.errors) {
          var errs = errRes.errors[prop];
          for (var i = 0; i < errs.length; i++) {
            msg = errs[i];
          }
        }
      }
      self.el.find('p.dlg-status').html(msg);
      self.el.find('p.dlg-status').addClass('error');
    });
    this.el.find('p.dlg-status').removeClass('error');
    this.el.find('p.dlg-status').html('Signing up...');
    return false;
  }
  
  RegisterController.prototype.didLoadDib = function() {
    this._dialog = new Dialog(this.el);
    this._dialog.overlay({closable: true});
  }

  return RegisterController;
});
