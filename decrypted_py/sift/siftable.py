#!/usr/bin/env python
# encoding: utf-8
"""
Representation of a block.

This module contains classes and data relating to the representation of a siftable.
"""

import os, re, types, collections, itertools, warnings
from util.decorators import *

import neighbors
import opcodes
import image
import util.math_ext
import util.events
import util.color
import util.decorators
import util.position
import _assets
import time

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
SCREEN_MAX_X = SCREEN_WIDTH - 1
SCREEN_MAX_Y = SCREEN_HEIGHT - 1
SCREEN_MIN_X = 0
SCREEN_MIN_Y = 0


ROTATION_MAX = (0xff >> 6)
SCALE_MAX = (0xff >> 2)

NULL_SIFTABLE_ID = 254

START_TILT = (1,1,2)

class Siftable(util.events.EventObject):
    """
    Representation of a physical Sifteo cube. Handles the
    interpretation of sensor events from the siftable to the
    app, and the sending of graphics and control messages
    from the app to the siftable.

    Siftable subclasses EventObject, meaning that it includes event methods. 
    In particular, a Siftable instance may trigger the following events:
        neighbor_add
        neighbor_remove
        flip_screendown
        flip_screenup
        tilt
        button
        button_press
        button_release
        (...and others. See opcodes.py for the full list.)
    """

    def __init__(self, id, root_set=None, send_method=None):
        """
        Create a Siftable object with the given ID. Siftable
        objects are not instantiated by apps directly; they
        are created internally and accessed through the
        app's sift set.
        """
        util.events.EventObject.__init__(self)
        self.id = id
        self.root_set = root_set
        if send_method is None:
            def send_method(*args):
                pass
        self.__send = send_method
        self.neighbors = neighbors.Neighbors()
        self.draw_count = 0
        self.button = False
        self._orientation = 0
        self.online = True
        self.tilt = START_TILT

    def initialize_state(self):
        self._send("ACCELEROMETER_TILT_REQUEST")
        self._send("BUTTON_REPORT_REQUEST")
        self._send("NEIGHBOR_REPORT_REQUEST")

    def idle(self, idling):
        """
        Displays either a blank white screen for before a game starts
        or the idle status screen.
        """
        if idling:
            p = 0
        else:
            p = 1
        self._send("GAME_START_STOP", p)

    def fill(self, *color):
        """
        Fills the siftable screen with a solid color.
        """
        c = util.color.Color(*color).rgb8
        self._send("GRAPHICS_FILL", c, draws=True)

    def rect(self, x, y, w, h, *color):
        """
        Draw a rectangle at top left corner x, y with width
        w and height h.
        """
        x, y, w, h = _limit_rect(x, y, w, h)    
        c = util.color.Color(*color).rgb8
        self._send("GRAPHICS_DRAW_RECT", *[int(n) for n in [x,y,c,w,h]],
                   draws=True)

    def image(self, img, x=0, y=0, sourceX=0, sourceY=0, 
              w=SCREEN_WIDTH, h=SCREEN_HEIGHT, scale=1, rotation=0, 
              app_id=0):
        """
        Draw a portion of an image.
        """
        # Lookup the actual image if it is a string or number
        if type(img) is not image.SiftImage:
            try:
                if type(img) is types.StringType:
                    base, extension = os.path.splitext(img)
                    img = base
                    if(extension != " "):
                        warnings.warn("referencing image with an extension." + 
                                          "Image names are now bundled into sftbndls.")                            
                        
                img = self.root_set.image_set[img]
            except _assets.AssetError:
                msg = "Image not found: %s" % img
                warnings.warn(msg)
                return None
            
        #offscreen
        if x > SCREEN_MAX_X or y > SCREEN_MAX_Y:
            return
        
        x = int( x )
        y = int( y )

        scale = util.math_ext.clamp(int(scale), 0, SCALE_MAX)
        rotation = int(rotation) % (ROTATION_MAX + 1)
        
        #allow x and y to be negative, just offset sourceX and sourceY instead
        #need to handle rotations as well
        if x < 0:
            if rotation == 1:
                sourceY -= x
                h += x
            elif rotation == 2:
                w += x
            elif rotation == 3:
                h += x
            else:
                sourceX -= x
                w += x
            x = 0
        if y < 0:
            if rotation == 1:
                w += y
            elif rotation == 2:
                h += y
            elif rotation == 3:
                sourceX -= y
                w += y
            else:
                sourceY -= y
                h += y
            y = 0
            
        if rotation == 1:
            if y + w > SCREEN_HEIGHT:
                sourceX += ( y + w - SCREEN_HEIGHT )
        elif rotation == 2:
            if x + w > SCREEN_WIDTH:
                sourceX += ( x + w - SCREEN_WIDTH )
            if y + h > SCREEN_HEIGHT:
                sourceY += ( y + h - SCREEN_HEIGHT )
        elif rotation == 3:
            if x + h > SCREEN_WIDTH:
                sourceY += ( x + h - SCREEN_WIDTH )
        
        if w < 0 or h < 0:
            return
        
        if rotation % 2 == 0:
            x, y, w, h = _limit_rect(x, y, w, h)
        else:
            x, y, h, w = _limit_rect(x, y, h, w)
        sourceX = int(sourceX)
        sourceY = int(sourceY)
        
        if self.root_set.instrumentPerformance:
            if hasattr(self.root_set, "totalTextureSize"):
                self.root_set.totalTextureSize += ( w * h )
                
            #warn users who are using horizontal strips
            #if sourceX > 0:
            #    print "PERFORMANCE WARNING, you appear to be using sprites in horizontal strips.  Use vertical for better performance"
               
        if self.root_set.app_id is not None:
            app_id = self.root_set.app_id
        args =  [app_id & 0xff, (app_id & 0xff00) >> 8,
                                (app_id & 0xff0000) >> 16,
                                (app_id & 0xff000000) >> 24]
        args += [img.index & 0xff, (img.index & 0xff00) >> 8,
                 int(x), int(y), 
                 sourceX & 0xff, (sourceX & 0xff00) >> 8,
                 sourceY & 0xff, (sourceY & 0xff00) >> 8,
                 int(w), int(h), (rotation << 6) | (scale & 0x3f)]
        self._send("GRAPHICS_IMAGE_TO_FRAMEBUFFER", *args)

    def repaint(self, r=None):
        """
        Manually repaint the siftable. Probably doesn't need
        to be called (make private?), since should be
        handled more efficiently as a batch call after every
        draw cycle.
        """
        if r is not None:
            self.orientation = r
        if(self.draw_count > 0):
            # the siftable counts rotation clockwise.
            rotation = [0, 3, 2, 1][self.orientation]
            self._send("GRAPHICS_DRAW", rotation, draws=False)
            self.draw_count = 0

    @property
    def face_down(self):
        """
        Boolean property indicating whether the block is flipped over.
        """
        return self.tilt[2] == 0

    @property
    def orientation(self):
        """
        The internal orientation of the siftable's display.
        0 is the "natural" orientation. Non-zero values
        represent 90-degree rotations of the internal
        display. For instance, if orientation is 1, the
        display is rotated such that "up" on the display
        points to the left side of the physical siftable.
        """
        return self._orientation

    @orientation.setter
    def orientation(self, value):
        new_orientation = value % 4
        if self._orientation != new_orientation:
            self.draw_count += 1
            self._orientation = new_orientation
            self.neighbors.orientation = self._orientation

    @staticmethod
    def opposite_of(index):
        """
        The index of the side opposite the indicated one.
        """
        return ((index + 2) % 4)

    def relative_alignment_of(self, s):
        """
        Returns the number of 90 degree clockwise rotations
        it would take for the given siftable to align with
        this one such that both of their "up" sides face the
        same way.

        Only computable if the two are neighbors. Raises an
        error if they are not neighbors.
        """
        try:
            my_direction = self.neighbors.direction_of(s)
            s_direction = s.neighbors.direction_of(self)
            return ((my_direction - s_direction - 2) % 4)
        except:
            msg = "%s and %s are not neighbors." % (self, s)
            raise Siftable.Error(msg, self)

    def relative_alignment_to(self, s):
        """
        Returns the number of 90 degree clockwise rotations
        it would take for this siftable to align with the given
        one such that both of their "up" sides face the same way.

        Only computable if the two are neighbors. Raises an
        error if they are not neighbors.
        """
        return s.relative_alignment_of(self)

    def group(self):
        """
        Returns a frozenset of all siftables in a contigous
        neighbor group with this one.
        """
        return frozenset(Siftable._Group(self))

    def position_of(self, siftable):
        """
        Returns the position of the given siftable relative
        to this one.

        Returns None if the siftable is not in the same
        group.
        """
        return Siftable._Group(self).position_of(siftable)

    def orient_group(self):
        """
        Rotates the orientation of all siftables in this
        siftable's group, so that the "up" sides for all
        siftables face the same way.

        Returns a frozenset of the group.
        """
        g = Siftable._Group(self)
        g.orient()
        return frozenset(g)

    def grid(self):
        """
        Create iterable grid of (Position,Siftable) pairs for
        all siftables that are grouped with this one.
        """
        return Siftable._Group(self).grid()

    def orient_to(self, s):
        """
        Changes this siftables orientation to match
        that of the given siftable.

        Only possible if the two are neighbors. Raises an
        error if they are not neighbors.
        """
        self.orientation += [0,3,2,1][self.relative_alignment_to(s)]

    def __repr__(self):
        return "sift-%d" % self.id

    class _Group(set):
        """
        A group is a contiguous cluster of neighbored siftables. A group has a 
        width and height, and has positions of all its siftables.
        
        Attributes
            center -- the Siftable object at the center of the group.
            positions -- dictionary of Position objects to Siftable objects.
            width -- width of the group, in Siftables
            height -- height of the group, in Siftables
        """

        def __init__(self, siftable):
            """
            Create a group with the given siftable at its
            center.
            """
            set.__init__(self, [siftable])
            self.center = siftable
            self.positions = {siftable: util.position.Position(0,0)}
            self.__add_neighbors(siftable)
            xvals, yvals = [sorted(s) for s in \
                            itertools.izip(*self.positions.values())]
            self.width = 1 + (xvals[-1] - xvals[0])
            self.height = 1 + (yvals[-1] - yvals[0])

        def position_of(self, siftable):
            """
            The position of the given siftable in this group. Returns a 
            Position instance.
            """
            try:
                return self.positions[siftable]
            except KeyError:
                return None

        def orient_to(self, siftable):
            """
            Apply orientation offset to all Siftable objects in the group, to 
            orient them to a specific member of the group.
            
            Parameters
                siftable -- the Siftable object to orient the group to.
            
            """
            assert siftable in self, "siftable %s not in group" % siftable
            visited = []
            def align_neighbors_to(siftable):
                visited.append(siftable)
                for n in siftable.neighbors:
                    if n is not None:
                        if n not in visited:
                            if n.orient_to(siftable):
                                align_neighbors_to(n)    
            align_neighbors_to(siftable)

        def orient(self):
            """
            Orient this group to its center Siftable 
            (from which it was created)
            """
            
            self.orient_to(self.center)

        def grid(self):
            """
            Generator for iteration through a group by position and siftable.
            """
            
            for siftable, position in self.positions.items():
                yield position, siftable

        def __add_neighbors(self, siftable, orientation=0):
            for i,n in enumerate(siftable.neighbors):
                if (n is not None) and (n not in self):
                    try:
                        self.add(n)
                        pos = self.positions[siftable].shift(i + orientation)
                        self.positions[n] = pos
                        try:
                            n_offset = siftable.relative_alignment_of(n) + orientation
                            self.__add_neighbors(n, n_offset)
                        except Siftable.Error:
                            pass
                    except Siftable.Error as e:
                        pass

    class Error(Exception):

        def __init__(self, msg, siftable):
            Exception.__init__(self, msg)

    # --- NON-API METHODS ----------------------------------------------------

    def _send(self, cmd, *params, **kparams):
        """
        Non-API method for sending a command to a siftable.
        """
        if self.online:
            if not (kparams.has_key("draws") and kparams["draws"] is False):
                self.draw_count += 1
            # print [int(opcodes.lookup(cmd)), self.id, params]

            if self.root_set.instrumentPerformance:
                if self.root_set.call_counts.has_key(cmd):
                    self.root_set.call_counts[cmd] += 1

                #time this so we can subtract it out of our game timings
                preSendTime = time.time()
                self.__send(int(opcodes.lookup(cmd)), self.id, params)
                postSendTime = time.time()
                diff = postSendTime - preSendTime
                self.root_set.radioTime += diff
            else:
                self.__send(int(opcodes.lookup(cmd)), self.id, params)

    def _update(self, msg):
        """
        Non-API method for updating siftable with numeric
        attributes. Attributes consist of neighbor IDs and
        accelerometer values.
        """
        op = msg.op
        if op is None:
            warnings.warn("Received unknown opcode %s (%s)" % (msg.op_id, msg))
            self.trigger("unknown", msg=msg)
            return
        if op.name == "neighbor":
            #warnings.warn("Received neighbor message, which should have been handled by SiftSet: %s (%s). Ignoring." % (msg.op_id, msg))
            return
        elif op.name == "tilt":
            new_tilt = tuple(msg.payload[0:3])
            flip_event = None
            if self.tilt != new_tilt:
                old_tilt = self.tilt
                self.tilt = new_tilt
                if old_tilt[2] != new_tilt[2]:
                    # print msg.payload
                    if msg.payload[2] < 1:
                        flip_event = "flip_screendown"
                    elif msg.payload[2] > 1:
                        flip_event = "flip_screenup"
                    # TODO - pending changes to fw, support neutral 0-1-2 
                    # z-axis
                    self.trigger(flip_event)
                self.trigger(op.name, tilt=new_tilt)
        elif op.name == "button":
            if(len(msg.payload) > 0):
                state = msg.payload[0]
                self.trigger("button", state=state)
                if state == 0 and self.button:
                    self.button = False
                    self.trigger("button_release")
                elif state == 1 and not self.button:
                    self.button = True
                    self.trigger("button_press")
            else:
                self.trigger("button")
        elif op.name == "shake":
            duration = None
            if msg.payload[0] is 1:
                self.trigger("shake", type="start", duration=None)
            else:
                #shake duration is next 2 bytes in payload
                duration = ( ( msg.payload[2] << 8 ) + msg.payload[1] ) / 1000.0
                self.trigger("shake", type="stop", duration=duration)
        else:
            self.trigger(op.name, msg=msg)

    def _add_neighbor(self, side, neighbor):
        """
        Add a neighbor to a side. Do not trigger events here.
        """
        if not side in xrange(len(neighbors.SIDE_NAMES)):
            #warnings.warn("side %s not valid" % side)
            return
        if neighbor in self.neighbors:
            #warnings.warn("Sift %s is already a neighbor on side %d"%(neighbor, self.neighbors.index(neighbor)))
            return
        self.neighbors.add_physical(side, neighbor)

    def _remove_neighbor(self, side):
        """
        Remove any neighbors from a side. Do not trigger events. No error if
        there isn't a neighbor to be removed.
        """
        if not side in xrange(len(neighbors.SIDE_NAMES)):
            #warnings.warn("side %s not valid" % side)
            return
        self.neighbors._physical_neighbors[side] = None


# --- MODULE HELPERS ---------------------------------------------

def _limit_point(x, y):
    x = util.math_ext.limit(x, SCREEN_MIN_X, SCREEN_MAX_X)
    y = util.math_ext.limit(y, SCREEN_MIN_Y, SCREEN_MAX_Y)
    return x, y

def _limit_rect(x, y, w, h):
    x,y = _limit_point(x,y)
    w = min(SCREEN_WIDTH - x, w)
    h = min(SCREEN_HEIGHT - y, h)
    # w = util.math_ext.limit(w, 0, SCREEN_MAX_X - x)
    # h = util.math_ext.limit(h, 0, SCREEN_MAX_Y - y)
    return (x, y, w, h)

  

