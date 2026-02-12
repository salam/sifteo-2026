#!/usr/bin/env python
# encoding: utf-8
"""
Collective siftable set handling.

This module contains classes and data pertaining to the set
of all siftables known to the system.
"""

import collections, re, time, os, glob, types
import itertools
import warnings

from util.decorators import *
from runner.connector.message import Message
from siftable import Siftable, NULL_SIFTABLE_ID
import neighbors, opcodes
import util.events

USB_DONGLE_ADDRESS = 0xff
# TODO - move this out of here.
# should be passed in or, better, never even needed

class SiftSet(collections.Sequence, util.events.EventObject):
    """
    Representation of a set of siftables. There will be one
    SiftSet per app, representing all siftables currently
    paired with the system's dongle.

    This class should not be instantiated directly by an
    app, but should only be accessed through the
    BaseApp.siftables member.

    A SiftSet fires the following events:
        new_siftable
        lost_siftable
        neighbor_change
    """

    def __init__(self, sift_ids, send_method, sound_set=None, image_set=None, app_id=None):
        """
        Initialize the set of siftables.
        """
        
        self._siftables = list()
        util.events.EventObject.__init__(self)
        self.sound_set = sound_set
        self.image_set = image_set
        self.send_method = send_method
        self.app_id = app_id
        # A dictionary of the state of sift neighbors based on unfiltered 
        # sensor messages. In a perfect world, each sift's neighbor state 
        # would match its neighbors._physical_neighbors, but there are lots of 
        # edge cases to be handled.
        self.neighbor_state = {}
        self.instrumentPerformance = False
        self._update_sift_ids(sift_ids)
        # set this flag to enable debug warnings.
        self._raise_warnings = False

    def __repr__(self):
        return repr(self._siftables)

    def __iter__(self):
        return iter(self._siftables)

    def __len__(self):
        return len(self._siftables)

    def __getitem__(self, i):
        return self._siftables[i]

    def __contains__(self, s):
        return s in self._siftables

    def repaint(self):
        """
        Send a repaint call to all siftables in this set.
        """
        [s.repaint() for s in self if s.draw_count]

    def strict_sequences(self):
        """
        Return all sequences, guaranteeing that each
        siftable is in one and only one sequence.
        """
        return self.sequences(True)

    def sequences(self, strict=False):
        """
        Return a list of all straight-line sequences of
        siftables in this set.

        A sequence is a list of siftables that are
        neighbored in a row or column. Sequences are sorted,
        but may run in any direction (left to right, down to
        up, etc.). A sequence may contain only one siftable.

        If strict is False, a siftable may show up in more
        than one sequence.
        """

        def _create_sequence(s1, s2, strict):
            if s2 is None:
                return [s1]
            elif strict and s2.neighbors.any_adjacent_to(s1):
                return None
            else:
                s3 = s2.neighbors.opposite_of(s1)
                new_sequence = _create_sequence(s2, s3, strict)
                if new_sequence:
                    return [s1] + new_sequence
                else:
                    return None

        def _already_sequenced(s1, s2, sequences):
            for seq in sequences:
                if set(seq) >= set([s1,s2]):
                    return True
            return False

        sequences = []
        for s in self:
            for n in s.neighbors:
                if n and not s.neighbors.opposite_of(n):
                    if not (strict and s.neighbors.any_adjacent_to(n)):
                        if not _already_sequenced(s,n,sequences):
                            new_sequence = _create_sequence(s,n, strict)
                            if new_sequence:
                                sequences.append(new_sequence)
        return sequences

    def groups(self):
        """
        Return a frozenset of all groups of adjacent siftables.

        See also Siftable.group().
        """
        groups = set()
        for s in self:
            if not [g for g in groups if s in g]:
                groups.add(s.group())
        return frozenset(groups)        
        
    def clear_event_handlers(self):
        """
        Detach all listeners from this SiftSet and from all
        Siftables in this set.
        """
        super(SiftSet, self).clear_event_handlers()
        for s in self:
            s.clear_event_handlers() 
                   
    # Non-API methods --------------------------------------------------------
    
    def _set_event_triggering(self, status):
        self._event_triggering = status
        for s in self:
            s._event_triggering = status
    
    def _find_by_id(self, id):
        """
        Non-API method for finding by ID. Returns None if nothing found.
        """
        matches = [s for s in self._siftables if s.id == id]
        if matches:
            return matches[0]

    def _update_sift_ids(self, sift_ids):
        for id in sift_ids:
            id = int(id)
            if id != USB_DONGLE_ADDRESS:
                s = self._find_by_id(id)
                if not s:
                    s = Siftable(id, self, self.send_method)
                    self.__add(s)
                    self.trigger("new_siftable", siftable=s)
                    s.initialize_state() #this sends messages back to the sift to request its current state.
        for s in self:
            if s.id not in sift_ids:
                self.__remove(s)
                self.trigger("lost_siftable", siftable=s)
    
    def _handle_lost_siftable(self, sift_id):
        s = self._find_by_id(sift_id)
        if s:
            def is_not_passed_sift(s): return s.id is not int(sift_id)
            def get_id(s): return s.id
            new_ids = map(get_id, filter(is_not_passed_sift, self._siftables))
            self._update_sift_ids(new_ids)
    
    def _handle_new_siftable(self, sift_id):
        s = self._find_by_id(sift_id)
        if not s:
            def get_id(s): return s.id
            new_ids = map(get_id, self._siftables)
            new_ids.append(int(sift_id))
            self._update_sift_ids(new_ids)

    def _update(self, msg):
        if msg:
            if msg.address == USB_DONGLE_ADDRESS:
                if msg.op_id == 1:
                    length = msg.payload[0]
                    self.update_sift_ids(msg.payload[1:1+length])
            elif msg.op and msg.op.name == "neighbor_full_report":
                self._handle_neighbor_full_report(msg)
            elif msg.op and msg.op.name == "neighbor":
                self._handle_neighbor_msg(msg)
            else:
                siftable = self._find_by_id(msg.address)
                if siftable:
                    siftable._update(msg)
                else:
                    if self._raise_warnings:
                        warnings.warn("Could not find Siftable %s" % msg.address)


    def _handle_neighbor_full_report(self, msg):
        """
        Translate a full neighbor report into individual neighbor messages.
        _handle_neighbor_msg() should filter the messages and turn any discrepancies into events.
        """
        neighbor_op = opcodes.lookup("neighbor")
        id = msg.address
        def f(side, ninfo):
            nid, nside = ninfo
            msg = Message.construct(neighbor_op, id, 0, side, nid, nside)
            self._handle_neighbor_msg(msg)
        f(2, msg.payload[0:2])
        f(3, msg.payload[2:4])
        f(0, msg.payload[4:6])
        f(1, msg.payload[6:8])


    def _handle_neighbor_msg(self, msg):
        id1 = msg.address
        side1, id2, side2 = msg.payload[0:3]
        sift1, sift2 = self._find_by_id(id1), None
        self.trigger("_neighbor_message", id=id1, side=side1, neighbor_id=id2, neighbor_side=side2)

        if not sift1:
            if self._raise_warnings:
                warnings.warn("Could not find Siftable %s" % msg.address)
            return
        if side1 not in xrange(len(neighbors.SIDE_NAMES)):
            if self._raise_warnings:
                warnings.warn("side %s not valid" % side1)
            return
        if id2 == NULL_SIFTABLE_ID:
            self._handle_neighbor_remove(id1, sift1, side1)
        else:
            self._handle_neighbor_add(id1, sift1, side1, id2, side2)

    def _handle_neighbor_add(self, id1, sift1, side1, id2, side2):
        """
        Verify and execute a neighbor arrival event.
        May generate neighbor removal events before the add, if the state of a sift is inconsistent.
        Siftables and games will be notified of the change as soon as the first member of a pair sends its arrival message.
        """
        sift2 = self._find_by_id(id2)
        if not sift2:
            if self._raise_warnings:
                warnings.warn("Could not find neighbor Siftable %s" % id2)
            return
        if side2 not in xrange(len(neighbors.SIDE_NAMES)):
            if self._raise_warnings:
                warnings.warn("side %s not valid" % side2)
            return

        self.neighbor_state[id1][side1] = id2

        if sift1.neighbors._physical_neighbors[side1] == sift2 and sift2.neighbors._physical_neighbors[side2] == sift1:
            # Nothing is changing; the first member of this pair already sent its message.
            return

        if sift2 in sift1.neighbors._physical_neighbors:
            oldside1 = sift1.neighbors._physical_neighbors.index(sift2)
            if oldside1 != side1:
                if self._raise_warnings:
                    warnings.warn("Moving %s on %s from side %d to %d"%(sift2, sift1, oldside1, side1))
                self._handle_neighbor_remove(id1, sift1, oldside1, force_remove=True)

        if sift1 in sift2.neighbors._physical_neighbors:
            oldside2 = sift2.neighbors._physical_neighbors.index(sift1)
            if oldside2 != side2:
                if self._raise_warnings:
                    warnings.warn("Moving %s on %s from side %d to %d"%(sift1, sift2, oldside2, side2))
                self._handle_neighbor_remove(id2, sift2, oldside2, force_remove=True)

        if sift1.neighbors._physical_neighbors[side1] is not None:
            if self._raise_warnings:
                warnings.warn("Overwriting existing neighbor on %s side %d"%(sift1, side1))
            self._handle_neighbor_remove(id1, sift1, side1, force_remove=True)

        if sift2.neighbors._physical_neighbors[side2] is not None:
            if self._raise_warnings:
                warnings.warn("Overwriting existing neighbor on %s side %d"%(sift2, side2))
            self._handle_neighbor_remove(id2, sift2, side2, force_remove=True)

        # Update sifts as soon as the first member of a pair sends its message. When the second member sends its own message, it will be swallowed.
        self._neighbor_add(id1, sift1, side1, id2, sift2, side2)

    def _handle_neighbor_remove(self, id1, sift1, side1, force_remove=False):
        """
        Verify and execute a neighbor departure.
        Siftables and games will not be notified of the change until both members of a pair have registered the departure.
        """
        self.neighbor_state[id1][side1] = None

        sift2 = sift1.neighbors._physical_neighbors[side1]
        if sift2:
            id2, side2 = sift2.id, None
            try:
                side2 = sift2.neighbors._physical_neighbors.index(sift1)
            except ValueError:
                pass
            if side2 is None:
                if self._raise_warnings:
                    warnings.warn("Trying to remove neighbor in a non-reciprocal relationship: sift1=%s, side1=%s, sift2=%s, side2=%s" % (sift1, side1, sift2, side2))
                return
        else:
            if self._raise_warnings:
                warnings.warn("Trying to remove non-existent neighbor from sift %s on side %s" % (sift1, side1))
            return

        if id2 not in self.neighbor_state.keys():
            if self._raise_warnings:
                warnings.warn("Trying to remove neighbor that no longer exists %s from sift %s"%(id2,id1))
            # even though sift2 is no longer a valid siftable, we have this dangling instance out there, so go ahead and update it.
            self._neighbor_remove(id1, sift1, side1, id2, sift2, side2)

        # Don't trigger events until both sifts have registered departures.
        elif force_remove or ((self.neighbor_state[id1][side1]==None) and (self.neighbor_state[id2][side2]==None)):
            self._neighbor_remove(id1, sift1, side1, id2, sift2, side2)

    def _neighbor_add(self, id1, sift1, side1, id2, sift2, side2):
        """
        Update neighbor state on the two siftables and trigger the appropriate events.
        """
        sift1._add_neighbor(side1, sift2)
        sift2._add_neighbor(side2, sift1)
        vs1 = sift1.neighbors._physical_to_virtual(side1)
        sift1.trigger("neighbor_add", neighbor=sift2, side=vs1)
        vs2 = sift2.neighbors._physical_to_virtual(side2)
        sift2.trigger("neighbor_add", neighbor=sift1, side=vs2)
        self.trigger("neighbor_change", type="add", siftable1=sift1, side1=vs1, siftable2=sift2, side2=vs2)

    def _neighbor_remove(self, id1, sift1, side1, id2, sift2, side2):
        """
        Update neighbor state on the two siftables and trigger the appropriate events.
        """
        sift1._remove_neighbor(side1)
        sift2._remove_neighbor(side2)
        vs1 = sift1.neighbors._physical_to_virtual(side1)
        sift1.trigger("neighbor_remove", neighbor=sift2, side=vs1)
        vs2 = sift2.neighbors._physical_to_virtual(side2)
        sift2.trigger("neighbor_remove", neighbor=sift1, side=vs2)
        self.trigger("neighbor_change", type="remove", siftable1=sift1, side1=vs1, siftable2=sift2, side2=vs2)


    def reset(self):
        self.clear_event_handlers()
        for s in self:
            s.clear_event_handlers()
            s.idle(True)
            
    # Private methods --------------------------------------------------------

    def __add(self, s):
        self._siftables.append(s)
        # s.idle(False)
        self.neighbor_state[s.id] = [None, None, None, None]
        s._event_triggering = self._event_triggering

    def __remove(self, s):
        del self.neighbor_state[s.id]
        for ns in self.neighbor_state.values():
            for i,nid in enumerate(ns):
                if nid == s.id:
                    ns[i] = None
        self._siftables.remove(s)


    # Deprecated methods -----------------------------------------------------

    @deprecated
    def play_music(self, song_name, volume=0.75, once=False):
        """ Deprecated. See sift.sound. """
        self.sound_set.play(song_name)

    @deprecated
    def pause_music(self):
        """ Deprecated. See sift.sound. """
        warnings.warn("pause_must not currently implemented")

    @deprecated
    def play_sound(self, sound_name):
        """ Deprecated. See sift.sound. """
        self.sound_set.play(sound_name)

