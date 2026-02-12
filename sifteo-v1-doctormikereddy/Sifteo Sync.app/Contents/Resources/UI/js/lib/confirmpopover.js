define(['popover',
        'class'],
function(Popover, clazz) {

  function ConfirmPopover(el, options) {
    options = options || {};
    ConfirmPopover.super_.call(this, el, options);
    
    var self = this
      , el = this.el;
    el.find('.ok').on('click', function(){
      self.emit('ok');
      self.hide(0, true);
      return false;
    });
    el.find('.cancel').on('click', function(){
      self.emit('cancel');
      self.hide(0, true);
      return false;
    });
  }
  clazz.inherits(ConfirmPopover, Popover);
  
  return ConfirmPopover;
});
