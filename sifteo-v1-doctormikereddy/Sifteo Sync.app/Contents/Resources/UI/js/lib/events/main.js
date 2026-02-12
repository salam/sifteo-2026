define(['exports', 'module',
        './lib/emitter'],
function(exports, module, Emitter) {
  exports = module.exports = Emitter;
  
  exports.Emitter =
  exports.EventEmitter = Emitter;
});
