import sys, os, ctypes
import helpers.asset_helper
from helpers.asset_iterator import AssetIterator
from uart_dongle import UART_Dongle

if len(sys.argv) != 2:
  print "use: asset_tree_delete <port>"
  exit(0)

class AssetDeletion(AssetIterator):
  def performAction(self, app_id, asset_id, asset_type, verbose):
    AssetIterator.performAction(self, app_id, asset_id, asset_type, verbose)
    if helpers.asset_helper.deleteAsset(self.dongle, self.siftID, app_id, asset_id, asset_type) is False:
      self.pushErrorMsg( "Asset Delete failed! app_id=%d asset_id=%d asset_type=%d" % (app_id, asset_id, asset_type) )
  


runner = AssetDeletion( UART_Dongle(int(sys.argv[1])), 0 )
runner.run()
runner.printErrorSummary()