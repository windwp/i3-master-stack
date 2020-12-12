
#!/usr/bin/env python3
#-----------------------------------------------
# Run some custom script when focust to specify window
#----------------------------------------------------

import i3ipc
import subprocess
from time import sleep
from pprint import pprint
import i3_master_layout


class I3FocusRun(object):
    def __init__(self, i3,isDebug):
        self.isDebug = isDebug
        self.i3 = i3
        self.isOnChrome = False
        pass

    def on_new(self, event):
        pass

    def on_master(self, newMasterId):
        pass
    def on_close(self, event):
        pass

    def on_move(self, event):
        pass

    def on_binding(self, event):
        pass

    def on_focus(self, event):
        window = self.i3.get_tree().find_focused()
        if (window.ipc_data["window_properties"]["instance"] == "google-chrome"):
            self.isOnChrome = True
            event.container.command(
                "exec xmodmap -e 'keycode 45 = k K k K NoSymbol NoSymbol'")
        elif (self.isOnChrome == True):
            self.isOnChrome = False
            event.container.command(
                "exec xmodmap -e 'keycode 45 = k K Up NoSymbol NoSymbol NoSymbol'")
            pass
        pass
    def on_tick(self, event):
        pass
