define(['./errors/uninstallerror',
        './errors/unpairerror',
        'events',
        'class'],
function(UninstallError, UnpairError, Emitter, clazz) {
  
  function Device(obj) {
    Device.super_.call(this);
    this._qtDevice = obj;
    this.init();
  }
  clazz.inherits(Device, Emitter);
  
  Device.prototype.init = function() {
    var self = this;
    
    this.__defineGetter__('name', function() {
      return self._qtDevice.name;
    });
    this.__defineSetter__('name', function(val) {
      self._qtDevice.name = val;
    });
    this.__defineGetter__('firmwareVersion', function() {
      return self._qtDevice.firmwareVersion;
    });
    this.__defineGetter__('storageAvailable', function() {
      return self._qtDevice.storageAvailable;
    });
    this.__defineGetter__('storageSize', function() {
      return self._qtDevice.storageSize;
    });
    this.__defineGetter__('isReady', function() {
      return self._qtDevice.isReady;
    });
    
    this.__defineGetter__('apps', function() {
      var apps = []
        , ailist = self._qtDevice.appInfoList
        , ai;
      for (var i = 0, len = ailist.length; i < len; i++) {
        ai = ailist[i];
        apps.push({ id: ai.id, version: ai.version, title: ai.title, size: ai.size, dataSize: ai.dataSize });
      }
      return apps;
    });
    
    this.__defineGetter__('pairedCubes', function() {
      var cubes = []
        , cilist = this._qtDevice.pairedCubeInfoList
        , ci;
      for (var i = 0, len = cilist.length; i < len; i++) {
        ci = cilist[i];
        cubes.push({ hwid: ci.hwid });
      }
      return cubes;
    });
    
    this._onready = onReady.bind(this);
    this._onpropertychanged = onPropertyChanged.bind(this);
    this._onappschanged = onAppsChanged.bind(this);
    this._onpairingschanged = onPairingsChanged.bind(this);
    this._onerror = onError.bind(this);
    this._qtDevice.onready.connect(this._onready);
    this._qtDevice.onpropertychanged.connect(this._onpropertychanged);
    this._qtDevice.onappschanged.connect(this._onappschanged);
    this._qtDevice.onpairingschanged.connect(this._onpairingschanged);
    this._qtDevice.onerror.connect(this._onerror);
  }
  
  Device.prototype.destroy = function() {
    this.removeAllListeners();
    if (this._onready) { this._qtDevice.onready.disconnect(this._onready); this._onready = null; }
    if (this._onpropertychanged) { this._qtDevice.onpropertychanged.disconnect(this._onpropertychanged); this._onpropertychanged = null; }
    if (this._onappschanged) { this._qtDevice.onappschanged.disconnect(this._onappschanged); this._onappschanged = null; }
    if (this._onpairingschanged) { this._qtDevice.onpairingschanged.disconnect(this._onpairingschanged); this._onpairingschanged = null; }
    if (this._onerror) { this._qtDevice.onerror.disconnect(this._onerror); this._onerror = null; }
    this._qtDevice = null;
  }
  
  Device.prototype.uninstall = function(id, cb) {
    var uninstaller = this._qtDevice.uninstall(id);
    uninstaller.onsuccess.connect(function() {
      return cb();
    });
    uninstaller.onerror.connect(function(code, message) {
      return cb(new UninstallError(message, code));
    });
    uninstaller.uninstall();
  }
  
  Device.prototype.unpair = function(cb) {
    var unpairer = this._qtDevice.unpair();
    unpairer.onsuccess.connect(function() {
      return cb();
    });
    unpairer.onerror.connect(function(code, message) {
      return cb(new UnpairError(message, code));
    });
    unpairer.unpair();
  }
  
  Device.prototype.promptUpdate = function() {
    this._qtDevice.promptUpdate();
  }
  
  
  function onReady() {
    this.emit('ready');
  }
  
  function onPropertyChanged(prop, val, oldVal) {
    this.emit('propertyChanged', prop, val, oldVal);
  }
  
  function onAppsChanged() {
    this.emit('appsChanged');
  }
  
  function onPairingsChanged() {
    this.emit('pairingsChanged');
  }
  
  function onError(code, message) {
    // TODO: Add code to error message
    this.emit('error', new Error(message));
  }
  
  return Device;
});
