define(['require', 'exports', 'module',
        './lib/system',
        './lib/apps',
        './lib/devices',
        './lib/cloud',
        './lib/settings',
        './lib/services'],
function(require, exports, module,
         system, apps, devices, cloud, settings, services) {
  exports = module.exports = system;
  exports.apps = apps;
  exports.devices = devices;
  exports.cloud = cloud;
  exports.settings = settings;
  exports.services = services;
});
