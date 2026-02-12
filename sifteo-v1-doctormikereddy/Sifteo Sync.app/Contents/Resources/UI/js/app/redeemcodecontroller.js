define(['wizard',
        'dialog',
        'popover',
        'dib',
        'controller',
        'siftsystem',
        'class'],
function(Wizard, Dialog, Popover, Dib, Controller, siftSystem, clazz) {
  
  function RedeemCodeController(options) {
    options = options || {};
    this._present = options.present;
    RedeemCodeController.super_.call(this);
  }
  clazz.inherits(RedeemCodeController, Controller);
  
  RedeemCodeController.prototype.template = 'redeem-code';
  
  RedeemCodeController.prototype.present = function(el) {
    this.view.show(el);
    this._wiz.attach('#redeem-code-form');
  }
  
  RedeemCodeController.prototype.onStep = function(step, i) {
    if ('submit' == step) {
      if (this._submitted) return;
      this._submitted = true;
      
      var self = this
        , el = this._inputEl
        , code = el.find('input[name="code"]').val();
      
      siftSystem.cloud.post({ code: code }, '/shop/redeem', function(res) {
        res.on('end', function() {
          var item = res.responseObject.items[0]
            , dib = new Dib('redeemed-for')
            , el;
          if (item.kind == 'credits') {
            el = dib.create({ iconURL: 'img/coins.png', message: 'You now have ' + item.amount + ' more credits!' });
            self._doneEl.append(el);
          } else if (item.kind == 'app') {
            var message = 'You can now play ' + item.title + '!';
            if (siftSystem.devices.active) {
              message += ' Scroll to ' + item.title + ' and click Install to put it on your Sifteo Base.';
            } else {
              message += ' Connect your Sifteo Base, scroll to ' + item.title + ' and click Install.';
            }
            
            el = dib.create({ iconURL: item.iconURL, message: message });
            self._doneEl.append(el);
          } else {
            el = dib.create({ message: 'You got something!' });
            self._doneEl.append(el);
          }
          self._wiz.to('done');
        });
      }).on('error', function(err) {
        var msg = err.message || 'Failed to redeem code.';
        if (err.responseObject) {
          var errRes = err.responseObject;
          if (errRes.message) {
            msg = errRes.message;
          }
          if (errRes.errors && errRes.errors.length) {
            msg = errRes.errors[0].message;
          }
        }
        self._errorEl.find('.message').html(msg);
        self._wiz.to('error');
      });
    }
  }
  
  RedeemCodeController.prototype.onStepped = function(step, i) {
    if ('done' == step) {
      this.el.find('.next').text('OK');
    } else if ('error' == step) {
      this.el.find('.next').text('Close');
    }
  }
  
  RedeemCodeController.prototype.onDone = function(step, i) {
    this.emit('done');
    this.view.hide();
    this.view.remove();
  }
  
  RedeemCodeController.prototype.willNext = function(step, i) {
    if ('input' == step) {
      var el = this._inputEl
        , verrs = [];
      var code = el.find('input[name="code"]').val();
      
      // validate that redemption code is not empty
      if (code.length < 1) {
        verrs.push({ selector: 'input[name="code"]' });
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
  
  RedeemCodeController.prototype.didLoadDib = function() {
    var wiz = new Wizard(this.el, { bodySelector: '.wizard-body' })
      , dib;
      
    this._wiz = wiz;
    dib = new Dib('redeem-code-step-input');
    this._inputEl = dib.create();
    dib = new Dib('redeem-code-step-submit');
    this._submitEl = dib.create({ message: 'Redeeming...' });
    dib = new Dib('redeem-code-step-done');
    this._doneEl = dib.create();
    dib = new Dib('redeem-code-step-error');
    this._errorEl = dib.create();
    
    wiz.step('input', this._inputEl)
       .step('submit', this._submitEl, { prevable: false, nextable: false })
       .step('done', this._doneEl, { prevable: false, final: true })
       .step('error', this._errorEl, { prevable: false, final: true });
    wiz.on('step', this.onStep.bind(this));
    wiz.on('stepped', this.onStepped.bind(this));
    wiz.on('done', this.onDone.bind(this));
    wiz.delegate = this;
    
    if (this._present == 'popover') {
      this.view = new Popover('wizard-popover', { id: 'redeem-code-popover', title: 'Redeem Code', position: 'south', fixed: true, autoRemove: false });
      this.view.overlay({ template: 'popover-overlay', closable: true });
    } else {
      this.view = new Dialog('wizard-dialog', { id: 'redeem-code-dialog', title: 'Redeem Code', autoRemove: false });
      this.view.overlay({ closable: true }).escapable();
    }
    
    this.view.content(this.el);
  }

  return RedeemCodeController;
});
