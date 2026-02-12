import os, time, random
import unittest
import fixtures
import testutil
import asset_helper
from nose.tools import *

class AssetTest(unittest.TestCase):
  def setUp(self):
    self.siftID = 0
    self.appID = 10
    self.assetID = 101
    self.imgfile_1 = testutil.getFixtureFile("walk.siftimg")
    self.imgfile_2 = testutil.getFixtureFile("small.siftimg")
    self.sndfile = testutil.getFixtureFile("beep0.wav")
    ok_( asset_helper.deleteAllAssets(fixtures.dongle, self.siftID, self.appID) )
  
  def testUploadMultipleAssetTypesReturnsCorrectCountsAndSizes(self):
    # this test only uploads image files - at the present time sound files are not supported 
    # by the blocks. Even so, the asset type tags are being tested here for completeness.
    ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
    ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_SOUND, self.imgfile_1) )
    countEnd   = asset_helper.queryAssetCount(fixtures.dongle, self.siftID, self.appID)
    eq_( 1, countEnd[0] ) # test image
    eq_( 1, countEnd[1] ) # test sound
    eq_( testutil.getFileSize( self.imgfile_1 )*2, countEnd[2] ) # test bytes used
  
  def testUploadMultipleAssetsReturnsInCorrectCountsAndSizes(self):
    image_1_count = int(random.random()*5+3)
    image_2_count = int(random.random()*5+3)
    size = testutil.getFileSize( self.imgfile_1 ) * image_1_count + testutil.getFileSize( self.imgfile_2 ) * image_2_count
    # upload a bunch of images
    for i in range(image_1_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i+10, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
    for i in range(image_2_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i+20, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_2) )
    # retreive asset status and verify
    count = asset_helper.queryAssetCount(fixtures.dongle, self.siftID, self.appID)
    eq_( image_1_count+image_2_count, count[0] ) # test image
    eq_( 0, count[1] ) # test sound
    eq_( size, count[2] ) # test bytes used
  
  def testOverwritingAnAssetResultsInCorrectStatus(self):
    # write a single asset ID
    ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
    # retreive asset status and verify
    count = asset_helper.queryAssetCount(fixtures.dongle, self.siftID, self.appID)
    eq_( 1, count[0] ) # test image
    eq_( testutil.getFileSize( self.imgfile_1 ), count[2] ) # test bytes used
    # re-write the same asset ID
    ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_2) )
    # retreive asset status and verify
    count = asset_helper.queryAssetCount(fixtures.dongle, self.siftID, self.appID)
    eq_( 1, count[0] ) # test image
    eq_( testutil.getFileSize( self.imgfile_2 ), count[2] ) # test bytes used
  
  def testDeleteAllAssetsResultsInZeroAssetCountsForApp(self):
    # upload multiple assets, then delete them
    for i in range(int(random.random()*5+3)):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
    ok_( asset_helper.deleteAllAssets(fixtures.dongle, self.siftID, self.appID) )
    # retreive asset status and verify
    count = asset_helper.queryAssetCount(fixtures.dongle, self.siftID, self.appID)
    eq_( 0, count[0] ) # test image
    eq_( 0, count[1] ) # test sound
    eq_( 0, count[2] ) # test bytes used
  
  def testDeletingSingleAssetReducesAssetCountByOne(self):
    # upload multiple assets, then delete them
    image_count = int(random.random()*5+3)
    for i in range(image_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
    delete_item = int(random.random()*image_count)
    ok_( asset_helper.deleteAsset(fixtures.dongle, self.siftID, self.appID, delete_item, asset_helper.ASSET_TYPE_IMAGE) )
    # retreive asset status and verify
    count = asset_helper.queryAssetCount(fixtures.dongle, self.siftID, self.appID)
    eq_( image_count-1, count[0] ) # test image
    eq_( testutil.getFileSize( self.imgfile_1 )*(image_count-1), count[2] ) # test bytes used
  
  def testAllWrittenAssetsVerifyCRC(self):
    asset_count = int(random.random()*5+3)
    asset_list = range(asset_count)
    # upload a bunch of images
    for i in asset_list:
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
    # no verify the CRC for each of the uploaded images
    for i in asset_list:
      result = asset_helper.verifyAsset(fixtures.dongle, self.siftID, self.appID, i, asset_helper.ASSET_TYPE_IMAGE)
      if result is False: continue
      if result[0] != result[1]:
        print "CRC ERROR: asset id=%d crc_orig=%d crc_calc=%d" % (i, result[0], result[1])
      ok_( result[0] == result[1] )
  
  def testAllWrittenAssetsAppearInAssetInventoryList(self):
    asset_count = int(random.random()*5+3)
    asset_list = []
    # upload a bunch of images
    for i in range(asset_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
      asset_list.append( "%d:%d" % (i, asset_helper.ASSET_TYPE_IMAGE) )
    # query the asset list and compare it with expected list
    result = asset_helper.queryAssetList(fixtures.dongle, self.siftID, self.appID)
    print "Assets uploaded: %s" % asset_list
    print "Assets queried:  %s" % result
    # compare the two lists
    ok_( testutil.allInSet(asset_list, result) )
  
  def testDeletedAssetDoesNotAppearInAssetInventoryList(self):
    asset_count = int(random.random()*5+3)
    delete_item = int(random.random()*asset_count)
    asset_list = []
    # upload a bunch of images, then delete one of them
    for i in range(asset_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, i, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
      if i != delete_item:
        asset_list.append( "%d:%d" % (i, asset_helper.ASSET_TYPE_IMAGE) )
    ok_( asset_helper.deleteAsset(fixtures.dongle, self.siftID, self.appID, delete_item, asset_helper.ASSET_TYPE_IMAGE) )
    # query the asset list and compare it with expected list
    result = asset_helper.queryAssetList(fixtures.dongle, self.siftID, self.appID)
    print "Delete asset = %d" % delete_item
    print "Assets uploaded: %s" % asset_list
    print "Assets queried:  %s" % result
    # compare the two lists
    ok_( testutil.allInSet(asset_list, result) )
    ok_( testutil.notInSet(["%d:%d" % (delete_item, asset_helper.ASSET_TYPE_IMAGE)], result) )
  
  def testAllWrittenAssetsAppearInAppInventoryList(self):
    app_count = int(random.random()*5+3)
    app_list = []
    # upload a bunch of images
    for i in range(1,app_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, i, 0, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
      app_list.append( i )
    # query the asset list and compare it with expected list
    result = asset_helper.queryAppList(fixtures.dongle, self.siftID)
    print "Apps uploaded: %s" % app_list
    print "Apps queried:  %s" % result
    # clean up the uploaded files
    for i in app_list:
      ok_( asset_helper.deleteAllAssets(fixtures.dongle, self.siftID, i) )
    # finally compare the two lists
    ok_( testutil.allInSet(app_list, result) )
  
  def testDeletedAssetDoesNotAppearInAppInventoryList(self):
    app_count = int(random.random()*5+3)
    delete_item = max(1, int(random.random()*app_count))
    app_list = []
    # upload a bunch of images, then delete one of them
    for i in range(1,app_count):
      ok_( asset_helper.uploadAsset(fixtures.dongle, self.siftID, i, 0, asset_helper.ASSET_TYPE_IMAGE, self.imgfile_1) )
      if i != delete_item:
        app_list.append( i )
    ok_( asset_helper.deleteAsset(fixtures.dongle, self.siftID, delete_item, 0, asset_helper.ASSET_TYPE_IMAGE) )
    # query the asset list and compare it with expected list
    result = asset_helper.queryAppList(fixtures.dongle, self.siftID)
    print "Delete asset = %d" % delete_item
    print "Apps uploaded: %s" % app_list
    print "Apps queried:  %s" % result
    # clean up the uploaded files
    for i in app_list:
      ok_( asset_helper.deleteAllAssets(fixtures.dongle, self.siftID, i) )
    # finally compare the two lists
    ok_( testutil.allInSet(app_list, result) )
    ok_( testutil.notInSet([delete_item], result) )
