import sys, os, ctypes
import helpers.asset_helper
from helpers.asset_iterator import AssetIterator
from uart_dongle import UART_Dongle

if len(sys.argv) != 2:
  print "use: asset_tree_verify <port>"
  exit(0)

class AssetDeletion(AssetIterator):
  def performAction(self, app_id, asset_id, asset_type, verbose):
    AssetIterator.performAction(self, app_id, asset_id, asset_type, verbose)
    result = helpers.asset_helper.verifyAsset(self.dongle, self.siftID, app_id, asset_id, asset_type)
    if result is False:
      self.pushErrorMsg( "CRC request failed! app_id=%d asset_id=%d asset_type=%d" % (app_id, asset_id, asset_type) )
    elif result[0] != result[1]:
      self.pushErrorMsg( "CRC ERROR! app_id=%d asset_id=%d crc_orig=%d crc_calc=%d" % (app, asset, result[0], result[1]) )
  


runner = AssetDeletion( UART_Dongle(int(sys.argv[1])), 0 )
runner.run()
runner.printErrorSummary()