define(function() {
  
  function Emitter() {
  }
  
  Emitter.prototype.emit = function(type) {
    // If there is no 'error' event listener then throw.
    if (type === 'error') {
      if (!this._events || !this._events.error ||
          (this._events.error instanceof Array && !this._events.error.length))
      {
        if (arguments[1] instanceof Error) {
          throw arguments[1]; // Unhandled 'error' event
        } else {
          throw new Error("Uncaught, unspecified 'error' event.");
        }
        return false;
      }
    }
    
    if (!this._events) return false;
    var handler = this._events[type];
    if (!handler) return false;
    
    if (typeof handler == 'function') {
      switch (arguments.length) {
        // fast cases
        case 1:
          handler.call(this);
          break;
        case 2:
          handler.call(this, arguments[1]);
          break;
        case 3:
          handler.call(this, arguments[1], arguments[2]);
          break;
        // slower
        default:
          var l = arguments.length;
          var args = new Array(l - 1);
          for (var i = 1; i < l; i++) args[i - 1] = arguments[i];
          handler.apply(this, args);
      }
      return true;
    } else if (handler instanceof Array) {
      var l = arguments.length;
      var args = new Array(l - 1);
      for (var i = 1; i < l; i++) args[i - 1] = arguments[i];

      var listeners = handler.slice();
      for (var i = 0, l = listeners.length; i < l; i++) {
        listeners[i].apply(this, args);
      }
      return true;
    } else {
      return false;
    }
  }
  
  Emitter.prototype.on =
  Emitter.prototype.addListener = function(type, listener) {
    if (!this._events) this._events = {};
    
    // To avoid recursion in the case that type == "newListener"! Before adding
    // it to the listeners, first emit "newListener".
    this.emit('newListener', type, listener);
    
    if (!this._events[type]) {
      // Optimize the case of one listener. Don't need the extra array object.
      this._events[type] = listener;
    } else if (this._events[type] instanceof Array) {
      // If we've already got an array, just append.
      this._events[type].push(listener);
    } else {
      // Adding the second element, need to change to array.
      this._events[type] = [this._events[type], listener];
    }
    
    return this;
  }
  
  Emitter.prototype.once = function(type, listener) {
    var self = this;
    self.on(type, function g() {
      self.off(type, g);
      listener.apply(this, arguments);
    });
  }
  
  Emitter.prototype.off = 
  Emitter.prototype.removeListener = function(type, listener) {
    if (!this._events || !this._events[type]) return this;
    
    var list = this._events[type];
    if (list instanceof Array) {
      var pos = -1;
      for (var i = 0, len = list.length; i < len; i++) {
        if (list[i] === listener) {
          pos = i;
          break;
        }
      }
      
      if (pos < 0) return this;
      list.splice(pos, 1);
      if (list.length == 0) {
        delete this._events[type];
      }
    } else if (this._events[type] === listener) {
      delete this._events[type];
    }
    
    return this;
  }
  
  Emitter.prototype.removeAllListeners = function(type) {
    if (!this._events) return this;

    // fast path
    if (!this._events.removeListener) {
      if (arguments.length === 0) {
        this._events = {};
      } else if (type && this._events && this._events[type]) {
        this._events[type] = null;
      }
      return this;
    }

    // slow(ish) path, emit 'removeListener' events for all removals
    if (arguments.length === 0) {
      for (var key in this._events) {
        if (key === 'removeListener') continue;
        this.removeAllListeners(key);
      }
      this.removeAllListeners('removeListener');
      this._events = {};
      return this;
    }

    var listeners = this._events[type];
    if (listeners instanceof Array) {
      while (listeners.length) {
        // LIFO order
        this.removeListener(type, listeners[listeners.length - 1]);
      }
    } else if (listeners) {
      this.removeListener(type, listeners);
    }
    this._events[type] = null;

    return this;
  }
  
  return Emitter;
});
