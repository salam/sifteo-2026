define(['./user',
        './errors/loginerror',
        'events',
        'class'],
function(User, LogInError, Emitter, clazz) {
  
  function System() {
    System.super_.call(this);
    this.init();
  }
  clazz.inherits(System, Emitter);
  
  System.prototype.init = function() {
    if (!window.siftSystem) return;
  
    if (siftSystem.user) {
      this.user = new User(siftSystem.user);
    }
    
    this._onload = onLoad.bind(this);
    this._onlogin = onLogIn.bind(this);
    this._onlogout = onLogOut.bind(this);
    this._onreset = onReset.bind(this);
    siftSystem.onload.connect(this._onload);
    siftSystem.onlogin.connect(this._onlogin);
    siftSystem.onlogout.connect(this._onlogout);
    siftSystem.onreset.connect(this._onreset);
  }
  
  System.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._onload) { siftSystem.onload.disconnect(this._onload); this._onload = null; }
    if (this._onlogin) { siftSystem.onlogin.disconnect(this._onlogin); this._onlogin = null; }
    if (this._onlogout) { siftSystem.onlogout.disconnect(this._onlogout); this._onlogout = null; }
    if (this._onreset) { siftSystem.onreset.disconnect(this._onreset); this._onreset = null; }
  }
  
  System.prototype.login =
  System.prototype.logIn = function(username, password, cb) {
    var auth = siftSystem.logIn(username, password);
    auth.onsuccess.connect(function() {
      return cb();
    });
    auth.onerror.connect(function(code, message) {
      return cb(new LogInError(message, code));
    });
  }
  
  System.prototype.logout =
  System.prototype.logOut = function() {
    siftSystem.logOut();
  }
  
  
  function onLoad() {
    this.emit('load');
  }
  
  function onLogIn() {
    this.user = new User(siftSystem.user);
    this.emit('login');
  }
  
  function onLogOut() {
    this.user.destroy();
    delete this.user;
    this.emit('logout');
  }
  
  function onReset() {
    this.emit('reset');
  }
  
  return new System();
});
