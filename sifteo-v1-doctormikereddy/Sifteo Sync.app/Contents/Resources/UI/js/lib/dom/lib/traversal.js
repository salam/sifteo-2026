define(['./collection',
        'selector'],
function(Collection, select) {

  // TODO: Use the exports.fname notation here.

  function find(selector) {
    var result;
    if (this.length == 1) {
      result = select(selector, this[0]);
    } else {
      // TODO: Implement support for multiple node collections.
    }
    return new Collection(result);
  }

  function parent() {
    return this.map(function(el) {
      return _relate(el, 'parentNode');
    });
  }
  
  function children() {
    var r = [], el;
    for (var i = 0, len = this.length; i < len; i++) {
      _siblings(this[i].firstChild, r);
    }
    return new Collection(r);
  }

  function next() {
    return this.map(function(el) {
      return _relate(el, 'nextSibling');
    });
  }
  
  function previous() {
    return this.map(function(el) {
      return _relate(el, 'previousSibling');
    });
  }
  
  function _relate(n, rel) {
    n = n[rel];
    while (n && n.nodeType !== 1) {
      n = n[rel];
    }
    return n;
  }
  
  function _siblings(n, r) {
    r = r || [];
    for ( ; n; n = n.nextSibling) {
      if (n.nodeType === 1) {
        r.push(n);
      }
    }
    return r;
  }
  
  return {
    find: find,
    parent: parent,
    children: children,
    next: next,
    previous: previous
  };
});
