define(['wizard',
        'dialog',
        'popover',
        'dib',
        'controller',
        'siftsystem',
        'class'],
function(Wizard, Dialog, Popover, Dib, Controller, siftSystem, clazz) {
  
  function AccountController(user, options) {
    options = options || {};
    this._user = user;
    this._present = options.present;
    AccountController.super_.call(this);
  }
  clazz.inherits(AccountController, Controller);
  
  AccountController.prototype.template = 'account';
  AccountController.prototype.events = {
    'click .cmd-logout': 'onLogOut'
  }
  
  AccountController.prototype.present = function(el) {
    this.view.show(el);
    this._wiz.attach('#account-form');
  }
  
  AccountController.prototype.onStep = function(step, i) {
    if ('submit' == step) {
      if (this._submitted) return;
      var self = this
        , el = this._detailsEl
      var givenName = el.find('input[name="name[given_name]"]').val()
        , familyName = el.find('input[name="name[family_name]"]').val()
        , password = el.find('input[name="password"]').val()
        , newPassword = el.find('input[name="new_password"]').val()
        , subscribe = el.find('input[name="subscribe"]:checked').val();
        
      var user = {};
      user.givenName = givenName;
      user.familyName = familyName;
      if (password.length) {
        user.password = password;
        user.newPassword = newPassword;
      }
      user.subscribe = subscribe ? true : false;

      this._submitted = true;
      siftSystem.cloud.put(user, '/users/me', function(res) {
        res.on('end', function() {
          //self._wiz.to('done');
          self.view.hide();
        });
      }).on('error', function(err) {
        var msg = err.message || 'Failed to update account.';
        if (err.responseObject) {
          var errRes = err.responseObject;
          if (errRes.message) {
            msg = errRes.message + '<br/>';
          }
          for (var prop in errRes.errors) {
            var errs = errRes.errors[prop];
            for (var i = 0; i < errs.length; i++) {
              msg += errs[i] + '<br/>';
            }
          }
        }
        self._errorEl.find('.message').html(msg);
        self._wiz.to('error');
      });
      return false;
    }
  }
  
  AccountController.prototype.onStepped = function(step, i) {
    if ('done' == step) {
      this.el.find('.next').text('OK');
    } else if ('error' == step) {
      this.el.find('.next').text('Close');
    }
  }
  
  AccountController.prototype.onDone = function(step, i) {
    this.view.hide();
  }
  
  AccountController.prototype.onLogOut = function(e) {
    siftSystem.logOut();
    // emitting and then hiding makes Qt 4.x unhappy
    //this.emit('logout');
    this.view.hide();
    return false;
  }
  
  AccountController.prototype.willNext = function(step, i) {
    if ('details' == step) {
      var el = this._detailsEl
        , verrs = [];
      var givenName = el.find('input[name="name[given_name]"]').val()
        , familyName = el.find('input[name="name[family_name]"]').val()
        , password = el.find('input[name="password"]').val()
        , newPassword = el.find('input[name="new_password"]').val()
        , newPasswordConfirmation = el.find('input[name="new_password_confirmation"]').val();
      
      // validate that new password is not empty
      if (password.length && newPassword.length < 1) {
        verrs.push({ selector: 'input[name="new_password"]' });
        verrs.push({ selector: 'input[name="new_password_confirmation"]' });
        this.el.find('a[href="#account-tab-password"]').tab('show');
      }

      // validate that new password is confirmed
      if (newPassword !== newPasswordConfirmation) {
        verrs.push({ selector: 'input[name="new_password"]' });
        verrs.push({ selector: 'input[name="new_password_confirmation"]' });
        this.el.find('a[href="#account-tab-password"]').tab('show');
      }
      
      el.find('.control-group').removeClass('error');
      
      if (verrs.length) {
        for (var i = 0, len = verrs.length; i < len; i++) {
          var verr = verrs[i];
          el.find(verr.selector).closest(verr.container || '.control-group').addClass('error');
        }
        return false;
      }
    }
    
    return true;
  }

  AccountController.prototype.didLoadDib = function() {
    var wiz = new Wizard(this.el, { bodySelector: '.wizard-body' })
      , dib;
      
    this._wiz = wiz;
    dib = new Dib('account-step-details');
    this._detailsEl = dib.create();
    dib = new Dib('account-step-submit');
    this._submitEl = dib.create({ message: 'Saving...' });
    dib = new Dib('account-step-done');
    this._doneEl = dib.create();
    dib = new Dib('account-step-error');
    this._errorEl = dib.create();
    
    var el = this._detailsEl;
    el.find('input[name="name[given_name]"]').val(this._user.givenName);
    el.find('input[name="name[family_name]"]').val(this._user.familyName);
    el.find('input[name="email"]').val(this._user.email);
    el.find('input[name="email"]').prop("disabled", true);
    el.find('input[name="subscribe"]').attr('checked', true);
    
    wiz.step('details', this._detailsEl)
       .step('submit', this._submitEl, { prevable: false, nextable: false })
       .step('done', this._doneEl, { prevable: false, final: true })
       .step('error', this._errorEl, { prevable: false, final: true });
    wiz.on('step', this.onStep.bind(this));
    wiz.on('stepped', this.onStepped.bind(this));
    wiz.on('done', this.onDone.bind(this));
    wiz.delegate = this;
    
    if (this._present == 'popover') {
      this.view = new Popover('wizard-popover', { id: 'account-popover', title: 'Account', position: 'south', fixed: true });
      this.view.overlay({ template: 'popover-overlay', closable: true });
    } else {
      this.view = new Dialog('wizard-dialog', { id: 'account-dialog', title: 'Account' });
      this.view.overlay({ closable: true });
    }
    
    this.view.content(this.el);
  }

  return AccountController;
});
