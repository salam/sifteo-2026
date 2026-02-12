import os, sys, struct
from nose.tools import *
import fixtures
import filecmp

def getFixtureFile(file):
  return os.path.realpath(os.path.join(fixtures.FIXTURE_PATH, file))

def diff_image_files( test_file, fixture_file ):
  return filecmp.cmp(test_file, fixture_file, shallow=False)

def getFileSize(path):
  return os.path.getsize(path)

def notInSet( item, items ):
  return( set(item) & set(items) == set([]) )

def allInSet( subset, superset ):
  return( set(subset) & set(superset) == set(subset) )

def makeAssetPath( appID, assetID ):
  app_id = "%010d" % appID
  asset_id = "%05d" % assetID
  path = os.path.join(".", "a", app_id, asset_id)
  try: os.makedirs( path )
  except: pass
  return path

def rgbToPixel(red, green, blue):
  b = int((blue/85 ) & 0x03) # convert from 8 bits => 2 bits
  g = int((green/36) & 0x07) # convert from 8 bits => 3 bits
  r = int((red/36  ) & 0x07) # convert from 8 bits => 3 bits
  return int(b | (g << 2) | (r << 5)) # assemble 8 bit pixel

def _bmp_write(header, image_bytes, filename):
  mn1 = struct.pack('<B',header['mn1'])
  mn2 = struct.pack('<B',header['mn2'])
  filesize = struct.pack('<L',header['filesize'])
  undef1 = struct.pack('<H',header['undef1'])
  undef2 = struct.pack('<H',header['undef2'])
  offset = struct.pack('<L',header['offset'])
  headerlength = struct.pack('<L',header['headerlength'])
  width = struct.pack('<L',header['width'])
  height = struct.pack('<L',header['height'])
  colorplanes = struct.pack('<H',header['colorplanes'])
  colordepth = struct.pack('<H',header['colordepth'])
  compression = struct.pack('<L',header['compression'])
  imagesize = struct.pack('<L',header['imagesize'])
  res_hor = struct.pack('<L',header['res_hor'])
  res_vert = struct.pack('<L',header['res_vert'])
  palette = struct.pack('<L',header['palette'])
  importantcolors = struct.pack('<L',header['importantcolors'])
  
  outfile = open(filename,'wb')
  outfile.write(mn1+mn2+filesize+undef1+undef2+offset+headerlength+width+height+\
          colorplanes+colordepth+compression+imagesize+res_hor+res_vert+\
          palette+importantcolors+image_bytes)
  outfile.close()

def _create_pixel( framebuffer, column, row, width, height, bpp ):
  b = g = r = 0
  dot = framebuffer[row * width + column]
  if bpp == 1: 
    # scale to 24 bit color
    b = int((dot & 0x03)     ) * 85
    g = int((dot & 0x1c) >> 2) * 36
    r = int((dot & 0xe0) >> 5) * 36
  return struct.pack('<BBB', b, g, r)

def frame_buffer_to_bmpfile( framebuffer, width, height, bpp, filename ):
  header = {
    'mn1':66,
    'mn2':77,
    'filesize':0,
    'undef1':0,
    'undef2':0,
    'offset':54,
    'headerlength':40,
    'width':width,
    'height':height,
    'colorplanes':1,
    'colordepth':24,
    'compression':0,
    'imagesize':0,
    'res_hor':0,
    'res_vert':0,
    'palette':0,
    'importantcolors':0
  }
  
  image_bytes = ''
  for row in range(height-1, -1, -1):# (BMPs are L to R from the bottom L row)
    for column in range(width):
      image_bytes = image_bytes + _create_pixel( framebuffer, column, row, width, height, bpp )
      row_mod = (width*header['colordepth']/8) % 4
      if row_mod == 0:
        padding = 0
      else:
        padding = (4 - row_mod)
      padbytes = ''
      for i in range(padding):
        x = struct.pack('<B',0)
        padbytes = padbytes + x
      image_bytes = image_bytes + padbytes
  
  _bmp_write(header, image_bytes, filename)

