define(['events',
        'class'],
function(Emitter, clazz) {
  
  function User(obj) {
    User.super_.call(this);
    this._qtUser = obj;
    this.init();
  }
  clazz.inherits(User, Emitter);
  
  User.prototype.init = function() {
    var self = this;
    this.__defineGetter__('familyName', function() {
      return self._qtUser.familyName;
    });
    this.__defineGetter__('givenName', function() {
      return self._qtUser.givenName;
    });
    this.__defineGetter__('email', function() {
      return self._qtUser.email;
    });
    this.__defineGetter__('balance', function() {
      return self._qtUser.balance;
    });
    
    this._onpropertychanged = onPropertyChanged.bind(this);
    this._qtUser.onpropertychanged.connect(this._onpropertychanged);
  }
  
  User.prototype.destroy = function() {
    this.removeAllListeners();
    if (this._onpropertychanged) { this._qtUser.onpropertychanged.disconnect(this._onpropertychanged); this._onpropertychanged = null; }
    this._qtUser = null;
  }
  
  
  function onPropertyChanged(prop, val, oldVal) {
    this.emit('propertyChanged', prop, val, oldVal);
  }
  
  return User;
});
