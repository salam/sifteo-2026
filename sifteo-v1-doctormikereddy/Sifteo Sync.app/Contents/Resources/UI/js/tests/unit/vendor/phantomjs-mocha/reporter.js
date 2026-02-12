define(function() {
  
  function Reporter(runner) {
    var total = runner.total
      , i = 1;
    
    runner.on('start', function() {
      send('start', { total: total });
    });
    
    runner.on('pass', function(test) {
      send('pass', { i: i, title: test.fullTitle() })
    });
    
    runner.on('pending', function(test) {
      send('pass', { i: i, title: test.fullTitle(), skip: true })
    });

    runner.on('fail', function(test, err){
      send('fail', { i: i, title: test.fullTitle() })
    });
    
    runner.on('test end', function() {
      ++i;
    });
    
    runner.on('end', function() {
      send('end');
    });
  }
  
  function send(event, test) {
    alert(JSON.stringify({ event: event, params: test }));
  }
  
  return Reporter;
});
