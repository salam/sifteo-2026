define(['view',
        'render',
        'class'],
function(View, render, clazz) {
  
  // TODO: Ensure that the metrics functions used in this view are available in
  //       minimal, non-jQuery DOM utilities (ex: Zepto, Bonzo, Anchor, etc.)
  
  function Tip(el, options) {
    options = options || {};
    Tip.super_.call(this, el, options);
    this.arrowEl = this.el.find(options.arrowSelector || '.arrow');
    this.className = options.className || 'tip';
    this._bodySel = options.bodySelector || options.contentSelector || '.body';
    this._fixed = options.fixed || false;
    this._padj = { top: 0, left: 0 };
    this._autoRemove = options.autoRemove !== undefined ? options.autoRemove : true;
    this.position(options.position || 'north');
  }
  clazz.inherits(Tip, View);
  
  Tip.prototype.body =
  Tip.prototype.content = function(el) {
    this.el.find(this._bodySel).empty().append(el);
    return this;
  };
  
  Tip.prototype.position = function(type) {
    this._position = type;
    return this;
  };
  
  Tip.prototype.attach = function(el, delay) {
    el = render.$(el); delay = delay || 0;
    this._attachedTo = el;
    this._onmouseenterel = mouseenterel.bind(this);
    this._onmouseleaveel = mouseleaveel.bind(this);
    this._onmouseentertip = mouseentertip.bind(this);
    this._onmouseleavetip = mouseleavetip.bind(this);
    
    // show tip on hover
    el.on('mouseenter', this._onmouseenterel);
    el.on('mouseleave', this._onmouseleaveel);
    
    // cancel hide on hover
    this.el.on('mouseenter', this._onmouseentertip);
    this.el.on('mouseleave', this._onmouseleavetip);
    
    function mouseenterel(e) { this.show(el); }
    function mouseleaveel(e) { this.hide(delay); }
    function mouseentertip(e) { this.cancelHide(); }
    function mouseleavetip(e) { this.hide(delay); }
  }
  
  Tip.prototype.unattach = function() {
    this._attachedTo.off('mouseenter', this._onmouseenterel);
    this._attachedTo.off('mouseleave', this._onmouseleaveel);
    this.el.off('mouseenter', this._onmouseentertip);
    this.el.off('mouseleave', this._onmouseleavetip);
    delete this._attachedTo;
  }
  
  Tip.prototype.show = function(el) {
    if (!el) throw new Error('Tip.show() element required');
    this.target = render.$(el);
    this.emit('show', this.target);
    this.el.appendTo(document.body);
    this.el.addClass('tip-' + this._position);
    this.reposition();
    this.el.removeClass('hide');
    this._reposition = this.reposition.bind(this);
    render.$(window).on('resize', this._reposition);
    render.$(window).on('scroll', this._reposition);
    return this;
  }
  
  Tip.prototype.hide = function(ms) {
    // duration
    if (ms) {
      this._hide = setTimeout(this.hide.bind(this), ms);
      return this;
    }
    
    // hide
    this.emit('hide');
    render.$(window).off('scroll', this._reposition);
    render.$(window).off('resize', this._reposition);
    this.el.addClass('hide');
    if (this._autoRemove) {
      var self = this;
      setTimeout(function() {
        self.remove();
        self.dispose();
      }, 10);
    }
    return this;
  }
  
  Tip.prototype.cancelHide = function() {
    if (!this._hide) return;
    clearTimeout(this._hide);
    delete this._hide;
  };
  
  Tip.prototype.remove = function() {
    if (this._attachedTo) {
      this.el.detach();
      return this;
    }
    return Tip.super_.prototype.remove.call(this);
  };
  
  
  /**
   * Reposition the tip if necessary.
   *
   * @api private
   */
  
  Tip.prototype.reposition = function() {
    var pos = this._position;
    var off = this.offset(pos);
    var newpos = this._fixed ? pos : this.suggested(pos, off);
    if (newpos) off = this.offset(pos = newpos);
    var adj = this.adjust(pos, off);
    this.replaceClass(pos);
    this.el.css({ top: off.top + adj.top, left: off.left + adj.left });
    if (adj.top || adj.left) {
      var ael = this.arrowEl;
      var ao = ael.offset();
      var padj = this._padj;
      ael.offset({ top: ao.top + padj.top - adj.top, left: ao.left + padj.left - adj.left });
      this._padj = adj;
    }
  };
  
  /**
   * Compute the offset for `.el`, relative to `.target`,
   * based on the given `pos`.
   *
   * @param {String} pos
   * @return {Object}
   * @api private
   */
   
  Tip.prototype.offset = function(pos) {
    var el = this.el;
    var target = this.target;

    var ew = el.outerWidth();
    var eh = el.outerHeight();

    var to = target.offset();
    var tw = target.outerWidth();
    var th = target.outerHeight();

    switch (pos) {
      case 'north':
        return {
          top: to.top - eh,
          left: to.left + tw / 2 - ew / 2
        }
      case 'north west':
        return {
          top: to.top,
          left: to.left - ew
        }
      case 'north east':
        return {
          top: to.top,
          left: to.left + tw
        }
      case 'south':
        return {
          top: to.top + th,
          left: to.left + tw / 2 - ew / 2
        }
      case 'south west':
        return {
          top: to.top + th - eh * .85,
          left: to.left - ew
        }
      case 'south east':
        return {
          top: to.top + th - eh * .85,
          left: to.left + tw
        }
      case 'east':
        return {
          top: to.top + th / 2 - eh / 2,
          left: to.left + tw
        }
      case 'west':
        return {
          top: to.top + th / 2 - eh / 2,
          left: to.left - ew
        }
      default:
        throw new Error('invalid position "' + pos + '"');
    }
  };
  
  Tip.prototype.adjust = function(pos, off) {
    var el = this.el;
    var ew = el.outerWidth();
    var eh = el.outerHeight();
    
    var win = render.$(window);
    var top = win.scrollTop();
    var left = win.scrollLeft();
    var w = win.width();
    var h = win.height();
    
    // TODO: Implement support for adjusting other positions.
    
    switch (pos) {
      case 'south':
        return {
          top: 0,
          left: off.left + ew > w ? 0 - (off.left + ew - w) - 12 : 0
        }
      default:
        return {
          top: 0,
          left: 0
        }
    }
  }
  
  /**
   * Compute the "suggested" position favouring `pos`.
   * Returns undefined if no suggestion is made.
   *
   * @param {String} pos
   * @param {Object} offset
   * @return {String}
   * @api private
   */
  
  Tip.prototype.suggested = function(pos, off) {
    var el = this.el;

    var ew = el.outerWidth();
    var eh = el.outerHeight();

    var win = render.$(window);
    var top = win.scrollTop();
    var left = win.scrollLeft();
    var w = win.width();
    var h = win.height();

    // too high
    if (off.top < top) return 'south';

    // too low
    if (off.top + eh > top + h) return 'north';

    // too far to the right
    if (off.left + ew > left + w) return 'west';

    // too far to the left
    if (off.left < left) return 'east';
  };
  
  /**
   * Replace position class `name`.
   *
   * @param {String} name
   * @api private
   */

  Tip.prototype.replaceClass = function(pos) {
    pos = pos.split(' ').join('-');
    this.el.attr('class', this.className + ' ' + pos + ' ' + (this._effect || ''));
  };
  
  return Tip;
});
