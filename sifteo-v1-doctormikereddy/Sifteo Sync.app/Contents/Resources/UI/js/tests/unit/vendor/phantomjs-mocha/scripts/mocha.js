var system = require('system')
  , webpage = require('webpage');

var page = webpage.create()
  , passes = 0
  , failures = 0
  , total;

page.onAlert = function(msg) {
  var a = JSON.parse(msg)
  switch(a.event) {
    case 'start':
      total = a.params.total;
      break;
    case 'pass':
      console.log('[  ok  ] ' + a.params.title)
      passes++;
      break;
    case 'fail':
      console.log('[ FAIL ] ' + a.params.title)
      failures++;
      break;
    case 'end':
      console.log('');
      if (failures) {
        console.log(failures + ' of ' + total + ' tests failed');
        phantom.exit(-1);
      } else {
        console.log(total + ' tests complete');
        phantom.exit();
      }
      break;
  }
}

page.onConsoleMessage = function(msg) {
  console.log(msg);
};

page.onError = function(msg, trace) {
  console.log(msg);
  trace.forEach(function(item) {
    console.log('    at ' + (item.function || '<anonymous>') + ' (' + item.file + ':' + item.line + ')');
  })
  phantom.exit(-1);
}

if (system.args.length === 1) {
  console.log('Usage: ' +  system.args[0] + ' page.html');
  phantom.exit(-1);
} else {
  var file = system.args[1];
  page.open(file, function (status) {
    if (status !== 'success') {
      console.log('Failed to load file: ' + file);
      phantom.exit(-1);
    } else {
      // tests will be run, with events delivered from the PhantomJS reporter
      // to page.onAlert
    }
  });
}
