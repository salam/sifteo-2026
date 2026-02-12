define({
  
  render: function(locals, options) {
    var html = this._template(locals, options);
    return this.html(html);
  }
  
});
