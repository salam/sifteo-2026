define(['./menucontroller',
        './librarycontroller',
        'dialog',
        './cdm',
        'siftsystem',
        'notifications',
        'jquery'],
function(MenuController, LibraryController, Dialog, cdm, siftSystem, notifications, jQuery) {
  var $ = jQuery;
  
  function MainController() {
    this.init();
  }
  
  MainController.prototype.init = function() {
    this._menuCtrl = new MenuController();
    this._libraryCtrl = new LibraryController();
    
    var self = this;
    
    siftSystem.on('load', function() {
      self._libraryCtrl = new LibraryController();
      self._libraryCtrl.el.appendTo('#main');
    });
    
    siftSystem.on('reset', function() {
      if (!self._libraryCtrl) return;
      self._libraryCtrl.destroy();
      self._libraryCtrl = null;
    });
    
    cdm.listen();
    
    notifications.on('unhandledError', function(notif) {
      var info = notif.info || {};
      
      if (info.error && info.error.code == 202) {
        var d = new Dialog('space-error-dialog');
        d.overlay({ closable: true }).escapable();
        d.el.find('.description').text('Whoops. Your Sifteo Base is too full.');
        if (info.suggestion) {
          d.el.find('.suggestion').text('Please click on the Sifteo Base icon in the upper right corner to remove a game and try again.');
        } else {
          d.el.find('.suggestion').hide();
        }
        d.show();
        return;
      }
      
      
      var d = new Dialog('error-dialog');
      d.overlay({ closable: true }).escapable();
      d.el.find('.description').text(info.description || 'Oh no. We have encountered an unexpected problem.');
      if (info.suggestion) {
        d.el.find('.suggestion').text(info.suggestion);
      } else {
        d.el.find('.suggestion').hide();
      }
      if (info.error) {
        var err = info.error;
        d.el.find('.message').text(err.message || '');
        d.el.find('.code').text(err.code || 'undefined');
      }
      
      d.show();
    })
  }
  
  MainController.prototype.run = function()  {
    this._menuCtrl.el.prependTo(document.body);
    this._libraryCtrl.el.appendTo('#main');
  }

  return MainController;
});
