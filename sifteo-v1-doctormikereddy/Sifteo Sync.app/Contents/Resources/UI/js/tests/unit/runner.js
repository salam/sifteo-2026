require.config({
  paths:{
    'app': '../js',
    'mocha': 'vendor/mocha/mocha',
    'chai': 'vendor/chai/chai'
  }
});

require(['require',
         'mocha',
         'chai'],
function(require, _mocha, _chai) {
  mocha.setup('bdd');
  
  require(['./suite'],
  function() {
    mocha.run();
  });
});
