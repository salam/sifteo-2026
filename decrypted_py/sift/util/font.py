#!/usr/bin/env python
"""
Font rendering classes.

This module contains classes pertaining to font rendering
using bitmapped sprite strips. Supports variable-width
fonts, horizontal and vertical alignment (left/center/right
or top/middle/bottom).
"""

import math, re, sys
from sift.siftable import SCREEN_MAX_X, SCREEN_MAX_Y, SCREEN_WIDTH

ALIGNMENT_LEFT = 0
ALIGNMENT_CENTER = 1
ALIGNMENT_RIGHT = 2
ALIGNMENT_TOP = 0
ALIGNMENT_MIDDLE = 1
ALIGNMENT_BOTTOM = 2

#using manually created font texture/metrics
FONT_TYPE_MANUAL = 0
#using bmfont
FONT_TYPE_BMFONT = 1

class Font:
    """
    Contains logic to paint text from a font strip to a cube.
    """

    def __init__(self, f):
        """
        Initialize the Font with a dict containing the
        font's metadata.

        The metadata must contain the following fields:

        strip:       The name of the image containing the
                     glyph graphics. This can be overridden
                     on a per-glyph basis (see metrics,
                     below). (FONT_TYPE_MANUAL only)

        strips:     a list of images that each glyph can index into.
                    (FONT_TYPE_BMFONT only)

        line_height: The height of a line, including room
                     for ascenders and descenders.

        leading:     Additional vertical space between lines
                     of text, in pixels.

        tracking:    Additional horizontal space between
                     glyphs, in pixels.

        metrics:
                     //FONT_TYPE_MANUAL
                     A dict of metrics for each glyph in the
                     font, indexed by unicode character.
                     Each glyph metric is tuple of form
                     [x,y,w], where x and y are the position
                     of the glyph on the sprite strip, and w
                     is the width of the glyph's sprite. The
                     glyph's height is assumed to be
                     line_height.

                     The glyph metric can have an optional
                     fourth parameter, an image name that
                     overrides the font's strip.
                     
                     //FONT_TYPE_BMFONT
                     
                     A dict of metrics for each glyph in the
                     font, indexed by unicode character.
                     Each glyph metric is tuple of form
                     [x,y,w,h,xoff,yoff,xadvance], where x and y are the position
                     of the glyph on the sprite strip, and w and h 
                     are the width/height of the glyph's sprite. xoff and yoff control
                     position adjustments per glyph.  xadvance controls spacing
                     between glyphs. 

        The following fields are optional:

        em: The em width of the font. If this is not
            specified, it is derived from the width of the
            "M" character. If there is no "M" in the font,
            it is set to the line_height.
        en: The en width of the font. If this is not
            specified, it is derived from the width of the
            "n" character. If there is no "n" in the font,
            it is set to half the line_height.
        """

        for k,v in f.iteritems():
            self.__dict__[k] = v

        if "em" not in self.__dict__.keys():
            if u"M" in self.metrics.keys():
                self.em = self.metrics["M"][2]
            else:
                self.em = self.line_height
        if "en" not in self.__dict__.keys():
            if u"n" in self.metrics.keys():
                self.en = self.metrics["n"][2]
            else:
                self.en = int(math.ceil(self.line_height/2.0))
                
        #default to manual fonts
        if "type" not in self.__dict__.keys():
            self.type = FONT_TYPE_MANUAL
            
        if self.type == FONT_TYPE_BMFONT:
            self.leading = 0
            self.tracking = 0

    def wrap_text(self, text, width, scale=1):
        """
        Break text up into lines such that each line fits
        within the specified width.
        """
        out = u''
        lines = text.split('\n')
        for line in lines:
            x = 0
            words = re.compile(' +').split(line)
            for word in words:
                word_width,word_height = self.measure_bounds(word, scale=scale, wrap=False)
                if x + word_width + self.tracking*scale > width:
                    if len(out) > 0 and out[-1] == u' ':
                        out = out[:-1]
                    out += u'\n'
                    x = 0
                out += word + u' '
                x += word_width + self.en
            if len(out) > 0 and out[-1] == u' ':
                out = out[:-1]
            out += u'\n'
        if len(out) > 0 and out[0] == u'\n':
            out = out[1:]
        out = re.sub('\s+$', '', out)
        return out

    def _build_lines(self, text, area=None, alignment=(ALIGNMENT_LEFT, ALIGNMENT_TOP), scale=1, rotation=0, character_wrap=False):
        x, y = 0, 0
        lines = []
        cur_line = []
        line_height = self.line_height * scale
        
        tracking = self.tracking * scale
        leading = self.leading * scale

        space_width = self.en * scale
        max_line_width = SCREEN_WIDTH
        if area:
            max_line_width = area[0]

        for i,c in enumerate(text):
            if unicode(c) == u"\n":
                lines.append(cur_line)
                cur_line = []
                y += line_height + leading
                x = 0

            elif unicode(c) == u" ":
                x += space_width + tracking
                if character_wrap and x >= max_line_width:
                    lines.append(cur_line)
                    cur_line = []
                    y += line_height + leading
                    x = 0

            elif unicode(c) in self.metrics:
                m = self.metrics[unicode(c)]
                spritex = m[0]
                spritey = m[1]
                spritewidth = m[2]
                
                if self.type == FONT_TYPE_MANUAL:
                    sprite = len(m) > 3 and m[3] or self.strip
                #only support a single sprite for bmfont right now
                else:
                    sprite = self.strips[ m[7] ]
                    xadvance = m[6]

                if character_wrap and x + spritewidth*scale >= max_line_width:
                    lines.append(cur_line)
                    cur_line = []
                    y += line_height + leading
                    x = 0
                
                if self.type == FONT_TYPE_MANUAL:
                    cur_line.append([
                        sprite,
                        x,
                        y,
                        spritex,
                        spritey,
                        spritewidth,
                        self.line_height, # not the scaled height, just the height on the sprite strip.
                        ])
                    
                    x += spritewidth*scale + tracking
                else:
                    xPos = x + m[4]*scale
                    yPos = y + m[5]*scale
                    
                    cur_line.append([
                        sprite,
                        xPos,
                        yPos,
                        spritex,
                        spritey,
                        spritewidth,
                        m[3]
                        ])
                    
                    x += xadvance*scale

            else:
                try:
                    print "[%s] not in font metrics table."%c
                except:
                    print "Character not in font metrics table."
                x += space_width + tracking
                if character_wrap and x >= max_line_width:
                    lines.append(cur_line)
                    cur_line = []
                    y += line_height + leading
                    x = 0

        if cur_line not in lines:
            lines.append(cur_line)

        if area:
            area = list(area)
        else:
            # Snap the area to the bounds of the text.
            area = [0,0]
            for line in lines:
                if len(line) > 0:
                    lastc = line[-1]
                    linew = lastc[1] + lastc[5]*scale + tracking
                    area[0] = max(area[0], linew)
            area[1] = (line_height + leading) * len(lines)

        yoffset = 0
        if alignment[1] == ALIGNMENT_MIDDLE:
            texth = (line_height + leading) * len(lines)
            yoffset = area[1]/2 - texth/2
        elif alignment[1] == ALIGNMENT_BOTTOM:
            texth = (line_height + leading) * len(lines)
            yoffset = area[1] - texth

        for line in lines:
            if len(line) > 0:
                lastc = line[-1]
                linew = lastc[1] + lastc[5]*scale + tracking
                xoffset = 0
                if alignment[0] == ALIGNMENT_CENTER:
                    xoffset = area[0]/2 - linew/2
                elif alignment[0] == ALIGNMENT_RIGHT:
                    xoffset = area[0] - linew
                for i in range(len(line)):
                    if xoffset:
                        line[i][1] += xoffset
                    if yoffset:
                        line[i][2] += yoffset

        for i,line in enumerate(lines):
            for j,char in enumerate(line):
                self._rotate_char(char, area, scale, rotation)

        return lines

    def _rotate_char(self, char, area, scale, rotation):
        awidth, aheight = area
        ox, oy = char[1], char[2]

        if rotation == 1:
            char[1] = oy
            char[2] = awidth - ox - char[5]*scale

        if rotation == 2:
            char[1] = awidth - ox - char[5]*scale
            char[2] = aheight - oy - char[6]*scale

        if rotation == 3:
            char[1] = aheight - oy - char[6]*scale
            char[2] = ox

    def measure_bounds(self, text, area=None, alignment=(ALIGNMENT_LEFT, ALIGNMENT_TOP), wrap=False, scale=1, rotation=0, character_wrap=False):
        """
        Return the width and height of the rendered text
        block, without actually rendering anything.
        """
        if area and wrap:
            text = self.wrap_text(text, area[0], scale=scale)
        w = h = 0
        lines = self._build_lines(text, area, alignment, scale=scale, rotation=rotation)
        for line in lines:
            h += self.line_height * scale + self.leading*scale
            if len(line) > 0:
                linew = line[-1][1] + line[-1][5]*scale + self.tracking*scale
                if linew > w:
                    w = linew
        return w,h

    def paint(self, siftable, inx, iny, text, area=None, alignment=(ALIGNMENT_LEFT, ALIGNMENT_TOP), wrap=False, scale=1, rotation=0, app_id=0, character_wrap=False):
        """
        Paint the text to the given siftable, starting at
        screen coordinates inx/iny.

        If area is specified as a width/height pair, the
        text will be constrained within a rectangle of that
        size. If it is not specified, it will be constrained
        to the full screen (128x128).

        If alignment is specified as a horizontal/vertical
        pair, text will be aligned according to the
        specified rules. The horizontal alignment is one of
        (ALIGNMENT_LEFT, ALIGNMENT_CENTER, ALIGNMENT_RIGHT),
        and the vertical alignment is one of (ALIGNMENT_TOP,
        ALIGNMENT_MIDDLE, ALIGNMENT_BOTTOM).

        If wrap is True AND an area is specified, text will
        be broken into lines so that all lines fit into the
        area's width.

        If character_wrap is True, then lines whose width
        exceeds either the specified area's width or 128
        pixels will be broken at the exceeding character.

        scale and rotation work similarly to
        Siftable.image().

        app_id is deprecated.
        """
        if area and wrap:
            text = self.wrap_text(text, area[0], scale=scale)
        lines = self._build_lines(text, area, alignment, scale=scale, rotation=rotation, character_wrap=character_wrap)
        for line in lines:
            for char in line:
                char[1] += inx
                char[2] += iny
                if char[1] >= 0-char[5] and char[1] <= SCREEN_MAX_X and char[2] >= 0-char[6] and char[2] <= SCREEN_MAX_Y:
                    siftable.image(*char, scale=scale, rotation=rotation)

