define(['wizard',
        'dialog',
        'popover',
        'dib',
        'controller',
        'siftsystem',
        'class'],
function(Wizard, Dialog, Popover, Dib, Controller, siftSystem, clazz) {
  
  function ShopController(options) {
    options = options || {};
    this._present = options.present;
    ShopController.super_.call(this);
  }
  clazz.inherits(ShopController, Controller);
  
  ShopController.prototype.template = 'shop';
  
  ShopController.prototype.present = function(el) {
    this.view.show(el);
    this._wiz.attach('#shop-form');
    
    if (this._loaded) return;
    this._loaded = true;
    
    var self = this;
    siftSystem.cloud.post({}, '/shop/session', function(res) {
      res.on('end', function() {
        var obj = res.responseObject
          , sid = obj.sid
          , products = obj.products || []
          , billingAddress
          , creditCard
          , phoneNumber
          , product
          , dib
          , el;
          
        if (obj.user) { billingAddress = obj.user.address; }
        if (obj.user) { creditCard = obj.user.creditCard; }
        if (obj.user) { phoneNumber = obj.user.phoneNumber; }

        self.el.find('input[name="sid"]').val(sid);

        for (var i = 0, len = products.length; i < len; i++) {
          product = products[i];
          dib = new Dib('shop-step-products-product');
          el = dib.create(product);
          if (i == 0) el.find('input[type="radio"]').attr('checked', true);
          self._productsEl.append(el);
        }

        if (billingAddress) {
          var el = self._billingAddressEl;
          if (billingAddress.name) {
            el.find('input[name="name[given_name]"]').val(billingAddress.name.givenName);
            el.find('input[name="name[middle_name]"]').val(billingAddress.name.middleName);
            el.find('input[name="name[family_name]"]').val(billingAddress.name.familyName);
          }
          el.find('input[name="address[street_address]"]').val(billingAddress.street);
          el.find('input[name="address[street_address_ext]"]').val(billingAddress.streetExt);
          el.find('input[name="address[locality]"]').val(billingAddress.locality);
          el.find('input[name="address[region]"]').val(billingAddress.region);
          el.find('input[name="address[postal_code]"]').val(billingAddress.postalCode);
          el.find('select[name="address[country]"]').val(billingAddress.country);
          el.find('input[name="phone_number"]').val(phoneNumber);
        }
        
        if (creditCard) {
          var el = self._creditCardEl;
          el.find('input[name="credit_card[name]"]').val(creditCard.name);
          el.find('input[name="credit_card[number]"]').val(creditCard.number);
          // Do not pre-fill the card security code (CSC), which should always
          // require manual entry.  For further details on this issue, see:
          //     https://sifteo.atlassian.net/browse/THWA-32
          //el.find('input[name="credit_card[csc]"]').val(creditCard.csc);
          var exp = creditCard.expiration || '';
          exp = exp.split('-');
          el.find('select[name="credit_card[expiration_date[month]]"]').val(exp[1]);
          el.find('select[name="credit_card[expiration_date[year]]"]').val(exp[0]);
          el.find('select[name="credit_card[type]"]').val(creditCard.type);
        }
        
        self._wiz.next();
      });
    }).on('error', function(err) {
      var msg = err.message || 'Failed to load products.';
      self._errorEl.find('.message').html(msg);
      self._wiz.to('error');
    });
  }
  
  ShopController.prototype.onStep = function(step, i) {
    if ('calculate' == step) {
      if (this._calculated) return;
      var self = this
        , obj = this._buildReq();
      
      this._calculated = true;
      siftSystem.cloud.put(obj, '/shop/session/' + obj.sid, function(res) {
        res.on('end', function() {
          var el = self._invoiceEl
            , obj = res.responseObject
            , items = obj.invoice.items
            , tax = obj.invoice.tax || {}
            , total = obj.invoice.total
            , creditCard
            , billingAddress
            , phoneNumber
            , dib;
          
          if (obj.user) { billingAddress = obj.user.address; }
          if (obj.user) { creditCard = obj.user.creditCard; }
          if (obj.user) { phoneNumber = obj.user.phoneNumber; }
          
          el.find('.items').empty();
          for (var i = 0, len = items.length; i < len; i++) {
            var item = items[i];
            item.price = item.price.toFixed(2);
            dib = new Dib('shop-step-invoice-item');
            el.find('.items').append(dib.create(item));
          }
          el.find('.tax .rate').html(tax.rate || '0.0');
          el.find('.tax .amount').html('$' + (tax.amount || 0).toFixed(2));
          el.find('.total .amount').html('$' + total.toFixed(2));
          
          el.find('.credit-card .number').html(creditCard.number)
          var exp = creditCard.expiration || '';
          exp = exp.split('-');
          el.find('.credit-card .expiration-month').html(exp[1])
          el.find('.credit-card .expiration-year').html(exp[0])
          
          el.find('.billing-address .given-name').html(billingAddress.name.givenName)
          el.find('.billing-address .family-name').html(billingAddress.name.familyName)
          el.find('.billing-address .street-address').html(billingAddress.street)
          el.find('.billing-address .street-address-ext').html(billingAddress.streetExt)
          el.find('.billing-address .locality').html(billingAddress.locality)
          el.find('.billing-address .region').html(billingAddress.region)
          el.find('.billing-address .postal-code').html(billingAddress.postalCode)
          el.find('.billing-address .country').html(billingAddress.country)
          el.find('.billing-address .phone-number').html(billingAddress.phoneNumber)
          
          self._wiz.to('invoice');
        });
      }).on('error', function(err) {
        var msg = err.message || 'Failed to purchase credits.';
        if (err.responseObject) {
          var errRes = err.responseObject;
          if (errRes.message) {
            msg = errRes.message + '<br/>';
          }
          if (errRes.errors && errRes.errors.length) {
            for (var i = 0, len = errRes.errors.length; i < len; i++) {
              var e = errRes.errors[i];
              msg += e.message + '<br/>';
            }
          }
        }
        self._errorEl.find('.message').html(msg);
        self._wiz.to('error');
      });
    } else if ('submit' == step) {
      if (this._submitted) return;
      var self = this
        , obj = this._buildReq();
      
      this._submitted = true;
      siftSystem.cloud.put(obj, '/shop/session/' + obj.sid + '/submit', function(res) {
        res.on('end', function() {
          self._doneEl.find('p').html('Thank you for your purchase!');
          self._wiz.to('done');
        });
      }).on('error', function(err) {
        var msg = err.message || 'Failed to purchase credits.';
        if (err.responseObject) {
          var errRes = err.responseObject;
          if (errRes.message) {
            msg = errRes.message + '<br/>';
          }
          if (errRes.errors && errRes.errors.length) {
            for (var i = 0, len = errRes.errors.length; i < len; i++) {
              var e = errRes.errors[i];
              msg += e.message + '<br/>';
            }
          }
        }
        self._errorEl.find('.message').html(msg);
        self._wiz.to('error');
      });
    }
  }
  
  ShopController.prototype.onStepped = function(step, i) {
    if ('invoice' == step) {
      this.el.find('.next').text('Submit');
    } else if ('done' == step) {
      this.el.find('.next').text('OK');
    } else if ('error' == step) {
      this.el.find('.next').text('Close');
    } else {
      this.el.find('.next').html('Next <i class="icon-chevron-right icon-white"></i>');
    }
  }
  
  ShopController.prototype.onDone = function(step, i) {
    this.emit('done');
    this.view.hide();
    this.view.remove();
  }
  
  ShopController.prototype.willNext = function(step, i) {
    if ('billing-address' == step) {
      var el = this._billingAddressEl
        , verrs = [];
      var givenName = el.find('input[name="name[given_name]"]').val()
        , familyName = el.find('input[name="name[family_name]"]').val()
        , streetAddress = el.find('input[name="address[street_address]"]').val()
        , locality = el.find('input[name="address[locality]"]').val()
        , region = el.find('input[name="address[region]"]').val()
        , postalCode = el.find('input[name="address[postal_code]"]').val()
        , phoneNumber = el.find('input[name="phone_number"]').val();
        
      if (givenName.length < 1) {
        verrs.push({ selector: 'input[name="name[given_name]"]' });
      }
      if (familyName.length < 1) {
        verrs.push({ selector: 'input[name="name[family_name]"]' });
      }
      if (streetAddress.length < 1) {
        verrs.push({ selector: 'input[name="address[street_address]"]' });
      }
      if (locality.length < 1) {
        verrs.push({ selector: 'input[name="address[locality]"]' });
      }
      if (region.length < 1) {
        verrs.push({ selector: 'input[name="address[region]"]' });
      }
      if (postalCode.length < 1) {
        verrs.push({ selector: 'input[name="address[postal_code]"]' });
      }
      if (phoneNumber.length < 1) {
        verrs.push({ selector: 'input[name="phone_number"]' });
      }
      
      el.find('input').removeClass('error');
      if (verrs.length) {
        for (var i = 0, len = verrs.length; i < len; i++) {
          var verr = verrs[i];
          el.find(verr.selector).addClass('error');
        }
        return false;
      }
    } else if ('credit-card' == step) {
      var el = this._creditCardEl
        , verrs = [];
      var name = el.find('input[name="credit_card[name]"]').val()
        , number = el.find('input[name="credit_card[number]"]').val()
        , csc = el.find('input[name="credit_card[csc]"]').val();
        
      if (name.length < 1) {
        verrs.push({ selector: 'input[name="credit_card[name]"]' });
      }
      if (number.length < 1) {
        verrs.push({ selector: 'input[name="credit_card[number]"]' });
      }
      if (csc.length < 1) {
        verrs.push({ selector: 'input[name="credit_card[csc]"]' });
      }
        
      el.find('input').removeClass('error');
      if (verrs.length) {
        for (var i = 0, len = verrs.length; i < len; i++) {
          var verr = verrs[i];
          el.find(verr.selector).addClass('error');
        }
        return false;
      }
    }
    
    return true;
  }
  
  ShopController.prototype.willPrev = function(step, i) {
    if ('invoice' == step) {
      this._calculated = false;
      return 'products';
    } else if ('error' == step) {
      this._calculated = false;
      return 'billing-address';
    }
    return true;
  }
  
  ShopController.prototype.didLoadDib = function() {
    var wiz = new Wizard(this.el, { bodySelector: '.wizard-body' })
      , dib;
    
    this._wiz = wiz;
    dib = new Dib('shop-step-load');
    this._loadEl = dib.create({ message: 'Loading...' });
    dib = new Dib('shop-step-products');
    this._productsEl = dib.create();
    dib = new Dib('shop-step-billing-address');
    this._billingAddressEl = dib.create();
    dib = new Dib('shop-step-credit-card');
    this._creditCardEl = dib.create();
    dib = new Dib('shop-step-calculate');
    this._calculateEl = dib.create({ message: 'Calculating sales tax...' });
    dib = new Dib('shop-step-invoice');
    this._invoiceEl = dib.create();
    dib = new Dib('shop-step-submit');
    this._submitEl = dib.create({ message: 'Submitting order...' });
    dib = new Dib('shop-step-done');
    this._doneEl = dib.create();
    dib = new Dib('shop-step-error');
    this._errorEl = dib.create();
    
    wiz.step('load', this._loadEl, { prevable: false, nextable: false })
       .step('products', this._productsEl, { prevable: false })
       .step('billing-address', this._billingAddressEl)
       .step('credit-card', this._creditCardEl)
       .step('calculate', this._calculateEl, { prevable: false, nextable: false, activity: true })
       .step('invoice', this._invoiceEl)
       .step('submit', this._submitEl, { prevable: false, nextable: false, activity: true })
       .step('done', this._doneEl, { prevable: false, final: true })
       .step('error', this._errorEl, { final: true });
    wiz.on('step', this.onStep.bind(this))
       .on('stepped', this.onStepped.bind(this))
       .on('done', this.onDone.bind(this));
    wiz.delegate = this;

    if (this._present == 'popover') {
      this.view = new Popover('wizard-popover', { id: 'shop-popover', title: 'Get More Credits', position: 'south', fixed: true, autoRemove: false });
      this.view.overlay({ template: 'popover-overlay', closable: true });
    } else {
      this.view = new Dialog('wizard-dialog', { id: 'shop-dialog', title: 'Get More Credits', autoRemove: false });
      this.view.overlay({ closable: true }).escapable();
      
      // NOTE: If the following lines are ommitted, rendering performance when
      //       showing and hiding elements in the wizard body suffers greatly.
      //       The DOM/CSS involved in this scenario should be investigated to
      //       determine the root cause.  Since this does not occur when viewing
      //       the wizard in a popover view, it is suspected that the modal CSS
      //       is causing the issue.
      //this.el.appendTo(document.body);
      //this.view.el.show();
      // END NOTE
    }
    
    this.view.content(this.el);
  }
  
  ShopController.prototype._buildReq = function() {
    var sid = this.el.find('input[name="sid"]').val();
    var el = this._productsEl;
    var productID = el.find('input[name="product[id]"]:checked').val()
      , productPrice = el.find('input[name="product[id]"]:checked').attr('data-price');
        el = this._billingAddressEl;
    var givenName = el.find('input[name="name[given_name]"]').val()
      , middleName = el.find('input[name="name[middle_name]"]').val()
      , familyName = el.find('input[name="name[family_name]"]').val()
      , street = el.find('input[name="address[street_address]"]').val()
      , streetExt = el.find('input[name="address[street_address_ext]"]').val()
      , locality = el.find('input[name="address[locality]"]').val()
      , region = el.find('input[name="address[region]"]').val()
      , postalCode = el.find('input[name="address[postal_code]"]').val()
      , country = el.find('select[name="address[country]"] option:selected').val()
      , phoneNumber = el.find('input[name="phone_number"]').val();
        el = this._creditCardEl;
    var ccName = el.find('input[name="credit_card[name]"]').val()
      , ccNumber = el.find('input[name="credit_card[number]"]').val()
      , ccCSC = el.find('input[name="credit_card[csc]"]').val()
      , ccExpirationMonth = el.find('select[name="credit_card[expiration_date[month]]"]').val()
      , ccExpirationYear = el.find('select[name="credit_card[expiration_date[year]]"]').val()
      , ccType = el.find('select[name="credit_card[type]"]').val();
    
    var billingAddress = {
      name: {
        familyName: familyName,
        givenName: givenName,
        middleName: middleName
      },
      street: street,
      streetExt: streetExt,
      locality: locality,
      region: region,
      postalCode: postalCode,
      country: country
    };
    var creditCard = {
      name: ccName,
      number: ccNumber,
      csc: ccCSC,
      expiration: ccExpirationYear + '-' + ccExpirationMonth,
      type: ccType
    };
    var products = [{
      id: productID,
      price: parseFloat(productPrice)
    }];
    
    var user = { address: billingAddress, phoneNumber: phoneNumber, creditCard: creditCard }
    
    return { sid: sid, user: user, products: products };
  }

  return ShopController;
});
