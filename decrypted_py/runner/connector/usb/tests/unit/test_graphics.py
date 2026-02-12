import os, time, shutil
import unittest
import fixtures
import testutil
import asset_helper
import graphics_helper

FB_IMAGE_NAME = 'test.bmp'
FB_IMAGE_PATH = os.path.join(os.path.dirname(os.path.realpath( __file__ )), "..", FB_IMAGE_NAME)

class GraphicsTest(unittest.TestCase):
  def setUp(self):
    self.siftID = 0
    self.appID = 10
    self.assetID = 0
    self.icons = testutil.getFixtureFile("icons.siftimg")
    self.colorCompressedImage = testutil.getFixtureFile("sifteo-logo-cc.siftimg")
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, testutil.rgbToPixel( 0, 255, 0 )) )
    self.assertTrue( asset_helper.deleteAllAssets(fixtures.dongle, self.siftID, self.appID) )
  
  def _download_and_save_frame_buffer(self, dongle, siftID, file):
    # TODO: call repaint logo
    frame_buffer = graphics_helper.downloadFrameBuffer(dongle, siftID)
    if frame_buffer is False: return False
    testutil.frame_buffer_to_bmpfile( frame_buffer[3], frame_buffer[0], frame_buffer[1], frame_buffer[2], file )
    return True
  
  def testDisplayAllPureColors(self):
    color = testutil.rgbToPixel( 0, 0, 0 ) # black
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_black.bmp") )
    color = testutil.rgbToPixel( 255, 0, 0 ) # red
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_red.bmp") )
    color = testutil.rgbToPixel( 0, 255, 0 ) # green
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_green.bmp") )
    color = testutil.rgbToPixel( 0, 0, 255 ) # blue
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_blue.bmp") )
    color = testutil.rgbToPixel( 0, 255, 255 ) # cyan
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_cyan.bmp") )
    color = testutil.rgbToPixel( 255, 0, 255 ) # magenta
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_magenta.bmp") )
    color = testutil.rgbToPixel( 255, 255, 0 ) # yellow
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_yellow.bmp") )
    color = testutil.rgbToPixel( 255, 255, 255 ) # white
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, color) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "pure_white.bmp") )
  
  def testSimpleSprite(self):
    self.assertTrue( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE, self.icons) )
    self.assertTrue( graphics_helper.paintColor(fixtures.dongle, self.siftID, testutil.rgbToPixel( 0, 255, 0 )) )
    self.assertTrue( graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 10, 10,  0,  0, 44, 41, 0, False) )
    self.assertTrue( graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 10, 77,  0, 41, 44, 41, 0, False) )
    self.assertTrue( graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 74, 10, 44,  0, 44, 41, 0, False) )
    self.assertTrue( graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 74, 77, 44, 41, 44, 41, 0, False) )
    self.assertTrue( graphics_helper.repaintDisplay( fixtures.dongle, self.siftID ) )
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    self.assertTrue( asset_helper.verifyAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE) )
    self.assertTrue( testutil.diff_image_files(FB_IMAGE_PATH, "simple_sprites.bmp") )
  
  # def testSimpleSpriteStressTest(self):
    # for i in range(50):
      # print "%03d: ******************************************************************" % i
      # if asset_helper.deleteAllAssets(fixtures.dongle, self.siftID, self.appID) is False:
        # print "WARNING: deleting assets failed"
      # if asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE, self.icons) is False:
        # print "ERROR: updloading asset"
        # continue
      # if graphics_helper.paintColor(fixtures.dongle, self.siftID, testutil.rgbToPixel( 0, 255, 0 )) is False:
        # print "ERROR: drawing color to screen"
        # continue
      # if graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 10, 10,  0,  0, 44, 41, 0, False) is False:
        # print "WARNING: didn't draw sprite 1"
      # if graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 10, 77,  0, 41, 44, 41, 0, False) is False:
        # print "WARNING: didn't draw sprite 2"
      # if graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 74, 10, 44,  0, 44, 41, 0, False) is False:
        # print "WARNING: didn't draw sprite 3"
      # if graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 74, 77, 44, 41, 44, 41, 0, False) is False:
        # print "WARNING: didn't draw sprite 4"
      # if graphics_helper.repaintDisplay( fixtures.dongle, self.siftID ) is False:
        # print "WARNING: repaint failed"
      # if asset_helper.verifyAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE) is False:
        # print "WARNING: CRC failed"
      # if self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) is False:
        # print "ERROR: download failed"
        # continue
      # if testutil.diff_image_files(FB_IMAGE_PATH, "simple_sprites.bmp") is False:
        # print "ERROR: image didn't match"
        # filename = "fail_%03d.bmp" % i
        # failpath = os.path.join(os.path.dirname(os.path.realpath( __file__ )), "..", filename)
        # shutil.copy(FB_IMAGE_PATH, failpath)
  
  def testSimpleColorCompressedImage(self):
    # clear the background to white
    graphics_helper.paintColor(fixtures.dongle, self.siftID, testutil.rgbToPixel( 255, 255, 255 ))
    # upload the compressed siftimg
    self.assertTrue( asset_helper.uploadAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE, self.colorCompressedImage) )
    # load the compressed siftimg
    self.assertTrue( graphics_helper.loadAssetIntoFrameBuffer(fixtures.dongle, self.siftID, self.appID, self.assetID, 1, 1, 1, 1, 126, 127, 0, False) )
    self.assertTrue( graphics_helper.repaintDisplay( fixtures.dongle, self.siftID ) )
    # grab the framebuffer
    self.assertTrue( self._download_and_save_frame_buffer(fixtures.dongle, self.siftID, FB_IMAGE_PATH) )
    # compare with test bitmap and save a copy if it fails
    if testutil.diff_image_files(FB_IMAGE_PATH, "logo.bmp") is False:
      print "ERROR: color compressed image didn't match"
      filename = "fail_colorCompression.bmp"
      failpath = os.path.join(os.path.dirname(os.path.realpath( __file__ )), "..", filename)
      shutil.copy(FB_IMAGE_PATH, failpath)
    # cleanup
    self.assertTrue( asset_helper.deleteAsset(fixtures.dongle, self.siftID, self.appID, self.assetID, asset_helper.ASSET_TYPE_IMAGE) )   