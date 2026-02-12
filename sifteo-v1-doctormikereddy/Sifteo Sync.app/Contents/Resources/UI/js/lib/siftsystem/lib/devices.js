define(['./device',
        'events',
        'class'],
function(Device, Emitter, clazz) {
  
  function Devices() {
    Devices.super_.call(this);
    this.active = null;
    this.init();
  }
  clazz.inherits(Devices, Emitter);
  
  Devices.prototype.init = function() {
    if (!window.siftSystem) return;
  
    if (siftSystem.devices.length > 0) {
      this.active = new Device(siftSystem.devices.at(0));
    }
    
    this._ondetected = onDetected.bind(this);
    this._onundetected = onUndetected.bind(this);
    siftSystem.devices.ondetected.connect(this._ondetected);
    siftSystem.devices.onundetected.connect(this._onundetected);
  }
  
  Devices.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._ondetected) { siftSystem.devices.ondetected.disconnect(this._ondetected); this._ondetected = null; }
    if (this._onundetected) { siftSystem.devices.onundetected.disconnect(this._onundetected); this._onundetected = null; }
  }
  
  
  function onDetected(qtdev) {
    var dev = new Device(qtdev);
    this.active = dev;
    this.emit('detected', dev);
  }
  
  function onUndetected(qtdev) {
    this.active.destroy();
    this.active = null;
    // TODO: Emit with argument set to the device instance that was unplugged.
    this.emit('undetected');
  }
  
  return new Devices();
});
