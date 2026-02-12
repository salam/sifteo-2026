# App module
# The App class is created from a path to an app and a link object.

import sys, os, json, inspect, traceback, time
from link import DONGLE_ADDRESS
import loader

try:
    import sift
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    import sift
from connector.message import Message
import sift.sound
import sift.sift_set
from sift.util.trace import SiftTraceException

try:
    from siftx import siftDebug
    from siftx import siftConsole
except:
    siftDebug = None
    siftConsole = None

# some reasonable recursion limit to prevent stack overflows
sys.setrecursionlimit(500);

# Dummy hostbridge, if not using Siftrunner
class DummyHost:
    def handleAppInitialized( self ):
        pass
    def handleAppStarted( self ):
        pass
    def handleAppReady( self ):
        pass
    def handleError( self, *args ):
        print args
        traceback.print_exc()
    


# --- App ---------------------------------------------------------------

class App:
    """
    An App is a bundle of code and assets hooked up to a link object. An app 
    object exposes tick, update, and cleanup methods, for use by a runner.
    """

    def __init__(self, path, link, sift_ids, app_id=None, data_path=None):
        """An application is created with a path, a link object, a collection of ints representing available siftable ids, and an optional app_id"""

        self.config = Config(path)
        self.link = link
        self.app_id = app_id
        self.data_path = data_path
        self.root_set = None
        self.app = None
        self.time = time.time()

        # Create the root set
        self.root_set = sift.sift_set.SiftSet(sift_ids,
                                        self.link.sendBuffered,
                                        self.config.sound_set,
                                        self.config.image_set,
                                        app_id=self.app_id)
        self.root_set._set_event_triggering(True)
        
        # Create the app from root_set, call setup if we have a setup method
        self.app = self.config.create_app(self.root_set, self.data_path)

        if siftDebug is not None and siftConsole is not None:
            self.app.debug = siftDebug
            self.app.console = siftConsole

        if hasattr(self.app, "setup"):
            try:
                self.app.setup()
            except SiftTraceException:
                # Catch the stack trace exception in case somebody uses it in setup()
                traceback.print_tb(sys.exc_info()[2])
            
        # Manually trigger new_siftable events after our app setup call.
        for s in self.root_set:
            self.root_set.trigger("new_siftable", siftable=s)

        self.prePauseSifts = []
        
        # if running with run.py
        if 'host' not in globals():
            global host
            host = DummyHost()


    def use_link(self, link):
        self.link = link

    def tick(self, dt):
        try:
            if self.app and hasattr(self.app, "tick"):
                curTime = time.time()
                delta = curTime - self.time
                if hasattr(self.app, "pre_tick"):
                    self.app.pre_tick()
                self.app.tick(delta)
                if hasattr(self.app, "post_tick"):
                    self.app.post_tick( delta )
                self.time = curTime
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2]);
            raise

    def update(self, *event):
        try:
            msg = Message.construct(*event)
            if msg.address == DONGLE_ADDRESS:
                # if it's from the dongle, we don't care.
                pass
            else:
                self.root_set._update(msg)
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])
            raise

    def cleanup(self):
        self.root_set.reset()

    def handle_lost_siftable(self, sift_id):
        try:
            if self.root_set is not None:
                self.root_set._handle_lost_siftable(sift_id)
                
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])

    def handle_new_siftable(self, sift_id):
        try:
            if self.root_set is not None:
                self.root_set._handle_new_siftable(sift_id)
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])

    def handle_will_stop(self):
        try:
            self.app.trigger("will_stop")
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])

    def handle_stop(self):
        try:
            self.app.trigger("stop")
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])

    def handle_pause(self):
        self.app.paused = True
        try:
            self.prePauseSifts = list( self.root_set._siftables )
            #print "Lost siftable, set before losing is ", self.prePauseSifts
            self.app.trigger("pause")
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])
        self.root_set._set_event_triggering(False)
        
    def handle_unpause(self):
        self.app.paused = False
        self.root_set._set_event_triggering(True)
        try:
            toDelete = [ x for x in self.prePauseSifts if x not in self.root_set._siftables ]
            #print "sifts to remove", toDelete
            for x in toDelete:
                self.root_set.trigger("lost_siftable", siftable=x)
                
            toAdd = [ x for x in self.root_set._siftables if x not in self.prePauseSifts ]
            #print "sifts to add", toAdd
            #print "all sifts", self.root_set._siftables
            for x in toAdd:
                #print "adding ", x
                self.root_set.trigger("new_siftable", siftable=x)

            #print "Unpausing, list of sifts is now ", self.root_set._siftables
            self.app.trigger("unpause")
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])
        self.time = time.time()

    def handle_sound_finished(self, file_name):
        try:
            self.app.trigger("sound_finished", file_name=file_name)
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])

    def handle_sound_started(self, file_name):
        try:
            self.app.trigger("sound_started", file_name=file_name)
        except BaseException as e:
            host.handleError(type(e), str(e), e, sys.exc_info()[2])

# --- Config ------------------------------------------------------------

class Config(object):
    """Configuration for an application"""

    def __init__(self, path):
        # Set up our paths
        self.base_path = os.path.abspath(path)
        self.src_path = self.base_path
        manifest_path = os.path.join(self.base_path, loader.MANIFEST_FILENAME)

        # Open our manifest to read values
        f = open(manifest_path)
        self.manifest_source = f.read()
        self._config = json.loads(self.manifest_source).values()[0]

        # Stick this app on the beginning of sys path, import
        sys.path.insert(0, self.src_path)
        module = __import__(self._config["appModule"])
        reload(module)

        # Pick out the appClass
        self.app_class = getattr(module, self._config["appClass"])

        # Set up our sound system
        try:
            sounds_path = os.path.join(self.base_path, 
                                       self._config["soundsPath"])
        except:
            sounds_path = None
        self.sound_set = sift.sound.SoundSet(sounds_path)

        # Set up our sound system
        try:
            images_path = os.path.join(self.base_path, 
                                       self._config["imagesPath"])
        except:
            images_path = None
        self.image_set = sift.image.ImageSet(images_path)
    
    def __getitem__(self, item):
        return self._config[item]
        
    def create_app(self, root_set, data_path):
        return self.app_class(root_set, self.image_set, self.sound_set, data_path)
    

### Test

import unittest

class AppTest(unittest.TestCase):
    def setUp(self):
        pass
    
    def testPath(self):
        app = App("../demos/sample_app", None)
        self.assertEqual(app.config["title"], "Super Sample App")
        assert(app.config.app_class is not None)


if __name__ == '__main__':
    
    unittest.main )
