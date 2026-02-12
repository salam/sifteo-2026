"""
Sound data classes.

This module contains classes pertaining to the management
and playing of sounds in SiftRunner. These classes will
usually be accessed through a BaseApp.
"""

import os, warnings
import _assets

try:
    import siftx
    _player = siftx.sound
except: 
    siftx = None
    class DummySiftSoundController:
        # Stub no-op implementation of SoundController. Only
        # exposed when this module is accessed outside the
        # context of SiftRunner.
        def playSound(self, path, volume): pass
        def playMusic(self, path, loop): pass
        def volume(self): return 0.0
        def setVolume(self, v): pass
        def pause(self): pass
        def resume(self): pass
        def stop(self): pass
    _player = DummySiftSoundController()
    warnings.warn("No sound library found.")

SOUND_FILE_PATTERN = "\.(wav|mp3)$"

class SoundSet(_assets._AssetSet):
    """
    A collection of sounds, and methods for accessing and controlling playback of those sounds. 
    """

    def __init__(self, sounds_path):
        """
        Traverses a directory and loads all known sound types.
        """
        _assets._AssetSet.__init__(self, sounds_path, Sound, 
                                         pattern=SOUND_FILE_PATTERN)
        self._app = None
        self._playing_sounds = dict()

    def _set_app(self, app):
        """
        Enables triggering of sound events on the app.
        """
        print "setting app to %s" % app
        self._app = app
        self._playing_sounds = dict()
        self._app.on("sound_started", self._handle_sound_started)
        self._app.on("sound_finished", self._handle_sound_finished)

    def play(self, id, volume=1.0):
        """
        Play the indicated sound cue at the given volume. Volume is a ratio of the sound's natural level, from 0 to 1.
        """
        _player.playSound(self[id].path, volume)

    def start(self, id, loop=False):
        """
        Load and play the indicated sound cue or music track, optionally 
        looping.

        Arguments:
            id -- the index or filename of the sound to be played
            loop -- optional boolean indicating whether the sound should be looped. Defaults to false.
        """
        _player.playMusic(self[id].path, loop)

    def is_playing(self, file_name):
        """
        Returns true if the sound of the given file_name is currently playing.

        Arguments:
            file_name -- specify the name of the file to be checked.
        """
        return file_name in self._playing_sounds and self._playing_sounds[file_name]

    def _handle_sound_started(self, event):
        self._playing_sounds[event["file_name"]] = True

    def _handle_sound_finished(self, event):
        self._playing_sounds[event["file_name"]] = False
    
    @property
    def volume(self):
        """
        The master volume for the sound player. Values range
        from 0 to 1.
        """
        return _player.volume()
    
    @volume.setter
    def volume(self, value):
        _player.setVolume(max(0.0, min(1.0, value)))

    def pause(self):
        """
        Pause all currently playing sounds.
        """
        _player.pause()

    def resume(self):
        """
        If paused, resume playing sounds.
        """
        _player.resume()

    def stop(self, id=None):
        """
        Stop sound playing.
        
        Arguments:
            id -- optional specific name or index of a sound to stop playing. If omitted, defaults to all.
        """
        if id is not None:
            _player.stop(self[id].path)
        else:
            _player.stop()
         
class Sound(_assets._Asset):
    """
    A single sound file. In general, this should not be instantiated directly.
    """

    def play(self, volume=1.0):
        """
        Play this sound cue at the given volume. Volume
        ranges from 0 to 1.
        """
        _player.sound(self.path, volume)
        
            
class Player(object):
    """
    The sound player. In general, this should not be instantiated directly.
    """

    def __init__(self, sound_set):
        self.sound_set = sound_set


