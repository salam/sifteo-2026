require.config({
  baseUrl: 'js/lib',
  paths: {
    'app': '../app',
    'bootstrap': '../../vendor/bootstrap/2.1.1/js/bootstrap',
    'hogan': '../../vendor/hogan/2.0.0/hogan-2.0.0'
  },
  packages: [
    { name: 'render' },
    { name: 'x-render', location: '../dev/render', main: 'main' },
    { name: 'x-render-mustache', location: '../dev/render-mustache', main: 'render-mustache' },
    { name: 'x-render-hogan', location: '../dev/render-hogan', main: 'render-hogan' },
    { name: 'x-view', location: '../dev/view', main: 'view' },
    { name: 'x-overlay', location: '../dev/overlay', main: 'overlay' },
    { name: 'x-tip', location: '../dev/tip', main: 'tip' },
    { name: 'x-popover', location: '../dev/popover', main: 'popover' },
    { name: 'x-carousel', location: '../dev/carousel', main: 'carousel' },
    { name: 'x-wizard', location: '../dev/wizard', main: 'wizard' }
  ],
  shim: {
    'bootstrap': {
      deps: ['jquery'],
      exports: 'jQuery.fn.modal'
    },
    'hogan': {
      exports: 'Hogan'
    }
  }
});

// FIXME: Move this out into a separate file.
// poly-fill - from the Mozilla Dev Center
if (!Function.prototype.bind) {  
  Function.prototype.bind = function (oThis) {  
    if (typeof this !== "function") {  
      // closest thing possible to the ECMAScript 5 internal IsCallable function  
      throw new TypeError("Function.prototype.bind - what is trying to be bound is not callable");  
    }  

    var aArgs = Array.prototype.slice.call(arguments, 1),   
        fToBind = this,   
        fNOP = function () {},  
        fBound = function () {  
          return fToBind.apply(this instanceof fNOP  
                                 ? this  
                                 : oThis || window,  
                               aArgs.concat(Array.prototype.slice.call(arguments)));  
        };  

    fNOP.prototype = this.prototype;  
    fBound.prototype = new fNOP();  

    return fBound;  
  };  
}

require(['app/app']);
