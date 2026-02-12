define(['dialog',
        'popover',
        'dib',
        'controller',
        'notifications',
        'class',
        'render'],
function(Dialog, Popover, Dib, Controller, notifications, clazz, render) {
  
  function BaseDeviceController(device, options) {
    options = options || {};
    this._device = device;
    this._present = options.present;
    BaseDeviceController.super_.call(this);
  }
  clazz.inherits(BaseDeviceController, Controller);
  
  BaseDeviceController.prototype.template = 'base-device';
  BaseDeviceController.prototype.events = {
    'submit': 'onClose',
    'click .cmd-close': 'onClose'
  }
  
  BaseDeviceController.prototype.present = function(el) {
    this.view.show(el);
  }
  
  /*
  BaseDeviceController.prototype.onSubmit = function() {
    var name = this.el.find('input[name="name"]').val();
    this._device.name = name;
    
    //this._dialog.hide();
  }
  */
  
  BaseDeviceController.prototype.onClose = function() {
    var name = this.el.find('input[name="name"]').val();
    this._device.name = name;
    
    this.view.hide();
    return false;
  }
  
  BaseDeviceController.prototype.onUninstall = function(e) {
    var item = render.$(e.target).closest('dd');
    var appID = item.find('.val-id').text();
    
    item.addClass('disabled');
    this._device.uninstall(appID, function(err) {
      if (err) {
        var info = {};
        info.suggestion = "Plug in your Sifteo Base and try again.";
        info.error = err;
        notifications.post('unhandledError', null, info);
        return;
      }
    });
    return false;
  }
  
  BaseDeviceController.prototype.onUnpair = function(e) {
    this._device.unpair(function(err) {
      if (err) {
        var info = {};
        info.suggestion = "Plug in your Sifteo Base and try again.";
        info.error = err;
        notifications.post('unhandledError', null, info);
        return;
      }
    });
    return false;
  }
  
  BaseDeviceController.prototype.willLoadDib = function() {
    return this._device;
  }
  
  BaseDeviceController.prototype.didLoadDib = function() {
    var self = this
      , device = this._device
      , dib;
    
    dib = new Dib('base-device-apps-tab');
    this._appsTabEl = dib.create();
    this.el.find('.tab-content').append(this._appsTabEl);
    
    dib = new Dib('base-device-cubes-tab');
    dib.events({ 'click .cmd-unpair': 'onUnpair' }, this);
    this._cubesTabEl = dib.create({ count: this._device.pairedCubes.length });
    this.el.find('.tab-content').append(this._cubesTabEl);
    
    device.formattedBytesAvailable = (device.storageAvailable / 1048576).toFixed(2);
    device.formattedSize = (device.storageSize / 1048576).toFixed(2);
    
    dib = new Dib('base-device-info-tab');
    this._infoTabEl = dib.create(this._device);
    this.el.find('.tab-content').append(this._infoTabEl);
    
    var apps = this._device.apps
      , app;
    for (var i = 0, len = apps.length; i < len; i++) {
      app = apps[i];
      if (app.id == 'com.sifteo.launcher') {
        this._infoTabEl.find('.val-launcher-version').text(app.version);
        continue;
      }
      dib = new Dib('base-device-app-item');
      dib.events({ 'click .cmd-uninstall': 'onUninstall' }, this)
      
      var totalSize = app.size + app.dataSize;
      app.formattedSize = (totalSize / 1048576).toFixed(2); // bytes -> MB
      app.formattedSizeUnit = 'MB';
      this._appsTabEl.find('dl').append(dib.create(app));
    }
    
    /*
    var cubes = this._device.pairedCubes
      , cube;
    for (var i = 0, len = cubes.length; i < len; i++) {
      cube = cubes[i];
      dib = new Dib('base-device-cube-item');
      this._cubesTabEl.find('#cube-list').append(dib.create(cube));
    }
    */
    
    this._device.on('propertyChanged', function(prop, val) {
      if (prop == 'firmwareVersion') {
        self._infoTabEl.find('.val-firmware-version').text(val);
      } else if (prop == 'storageAvailable') {
        var formattedBytesAvailable = (val / 1048576).toFixed(2);
        self._infoTabEl.find('.val-storage-available').text(formattedBytesAvailable);
      }
    })
    
    this._device.on('appsChanged', function() {
      self._appsTabEl.find('dl').empty();

      var apps = self._device.apps
        , app
        , dib;
      for (var i = 0, len = apps.length; i < len; i++) {
        app = apps[i];
        if (app.id == 'com.sifteo.launcher') {
          self._infoTabEl.find('.val-launcher-version').text(app.version);
          continue;
        }
        dib = new Dib('base-device-app-item');
        dib.events({ 'click .cmd-uninstall': 'onUninstall' }, self);
        self._appsTabEl.find('dl').append(dib.create(app));
      }
    });
    
    this._device.on('pairingsChanged', function() {
      self._cubesTabEl.find('.val-pairings-count').text(self._device.pairedCubes.length);
      /*
      self._cubesTabEl.find('#cube-list').empty();
      
      var cubes = self._device.pairedCubes
        , cube
        , dib;
      for (var i = 0, len = cubes.length; i < len; i++) {
        cube = cubes[i];
        dib = new Dib('base-device-cube-item');
        self._cubesTabEl.find('#cube-list').append(dib.create(cube));
      }
      */
    });
    
    if (this._present == 'popover') {
      this.view = new Popover('wizard-popover', { id: 'device-popover', title: 'Sifteo Cubes', position: 'south', fixed: true });
      this.view.overlay({ template: 'popover-overlay', closable: true });
    } else {
      this.view = new Dialog('wizard-dialog', { id: 'device-dialog', title: 'Sifteo Cubes' });
      this.view.overlay({ closable: true });
    }
    
    this.view.content(this.el);
  }
  
  return BaseDeviceController;
});
