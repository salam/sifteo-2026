define(['siftsystem'],
function(siftSystem) {

  describe("siftsystem", function() {
    
    it('should export apps', function() {
      expect(siftSystem.apps).to.exist;
      expect(siftSystem.apps).to.be.an('object');
    });
    
    it('should export devices', function() {
      expect(siftSystem.devices).to.exist;
      expect(siftSystem.devices).to.be.an('object');
    });
    
    it('should export cloud', function() {
      expect(siftSystem.cloud).to.exist;
      expect(siftSystem.cloud).to.be.an('object');
    });
    
  });
  
  return { name: "test.siftsystem" }
});
