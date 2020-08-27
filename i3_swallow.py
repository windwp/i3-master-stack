#!/usr/bin/env python3
#-----------------------------------------------
# used to swallow a terminal window in i3
# this process is check automatic in i3
# When i3 have new window it will check parent process 
# and if it find a parent process have same id in current workspace it will swallow it
#----------------------------------------------------

import i3ipc
import subprocess
from time import sleep
from pprint import pprint
import i3_master_layout


class I3Swallow(object):
    def __init__(self, i3, terminal, masterTag, masterHander: i3_master_layout.I3MasterLayout):
        self.i3 = i3
        self.terminal = terminal
        self.masterTag = masterTag
        self.masterHandler = masterHander
        self.swallowDict = {}
        self.nextSwallowId = 0 
        self.masterHandler.on("master_change", self.on_master)
        pass

    def unMarkAllNode(self, node, marked):
        for mark in node.marks:
            if mark == marked:
                self.i3.command('[con_id=%s] unmark %s' % (node.id, marked))
                return True
        for node in node.nodes:
            if(self.unMarkAllNode(node, marked)):
                return True
        return False

    def checkNodeIsMater(self, node):
        if(self.masterTag != None):
            for mark in node.marks:
                if(mark.startswith(self.masterTag)):
                    return True
        return False

    def hideSwallowParent(self, node, windowId, swallow):
        if(str(node.window) == str(windowId)):
            self.i3.command('[con_id=%s] mark --add %s' %
                            (node.parent.id, "swallow"+str(node.id)))
            self.i3.command('[con_id=%s] move to scratchpad' % node.id)
            # check use master layout
            isMaster = self.checkNodeIsMater(node)

            self.i3.command('[con_id=%s] focus' % swallow.id)
            self.swallowDict[str(swallow.id)] = {
                "id": node.id,
                "layout": node.layout,
                "index": node.parent.nodes.index(node),
                "isMaster": isMaster,
                # minus to hidden window,
                "parent_nodes": len(node.parent.nodes)-1,
            }

            self.masterHandler.isSwallowNext = True
            if(isMaster == True):
                self.masterHandler.resizeMaster(swallow.id)
            return True
        for node in node.nodes:
            if(self.hideSwallowParent(node, windowId, swallow)):
                return True
        return False

    def getParentNodePid(self, node):
        # get parent of pid because terminal spwan shell(zsh or fish) and then spawn that child process
        output = subprocess.getoutput(
            "ps -o ppid= -p $(ps -o ppid= -p $(xprop -id %d _NET_WM_PID | cut -d' ' -f3 ))" % (node.window))
        return output

    def getWindowIdfromPId(self, pid):
        output = subprocess.getoutput("xdotool search -pid %s" % pid)
        return output

    def on_master(self, newMasterId):
        for key in self.swallowDict:
            item = self.swallowDict.get(key)
            if(item["id"] == newMasterId):
                item["isMaster"] = True
            else:
                item["isMaster"] = False
        pass

    def on_new(self, event):
        if event.container.name != self.terminal:
            workspace = self.i3.get_tree().find_focused().workspace()
            if(self.nextSwallowId != 0):
                parentContainer = workspace.find_by_window(self.nextSwallowId)
                if(parentContainer != None):
                    self.hideSwallowParent(
                        parentContainer, self.nextSwallowId, event.container)
                    self.nextSwallowId = 0
                    return

            self.nextSwallowId = 0
            # if we can find parent node have pid  map to any node in workspace we will hide it
            # TODO change it to check class name of this application and if that class name belong to a list of swallow name then we will swallow it
            # the process  for check parent pid is slow
            parentContainerPid = self.getParentNodePid(event.container)
            #id of root
            if(parentContainerPid != "      1" and len(parentContainerPid) < 9):
                parentContainerWid = self.getWindowIdfromPId(
                    parentContainerPid)
                for item in workspace.nodes:
                    self.hideSwallowParent(
                        item, parentContainerWid, event.container)
        pass

    def on_close(self, event):
        swallow = self.swallowDict.get(str(event.container.id))
        if swallow != None:
            workspace = self.i3.get_tree().find_focused().workspace()
            window = self.i3.get_tree().find_by_id(swallow["id"])
            if window != None:
                mark = "swallow"+str(swallow['id'])
                del self.swallowDict[str(event.container.id)]
                self.i3.command(
                    '[con_id=%s] scratchpad show;floating disable;focus' % (window.id))
                # try to restore to the original position
                if(swallow['isMaster'] == False):
                    self.i3.command(
                        '[con_id=%s] move container to mark %s' % (window.id, mark))
                parentMarked = workspace.find_marked(mark)
                targetWindow = None
                if(len(parentMarked) > 0):
                    self.i3.command('[con_id=%s] unmark %s' %
                                    (parentMarked[0].id, mark))

                if(targetWindow == None and len(parentMarked) > 0 and len(parentMarked[0].nodes) > 0):
                    if (swallow["index"] < len(parentMarked[0].nodes)):
                        targetWindow = parentMarked[0].nodes[swallow['index']]

                if(targetWindow != None):
                    self.i3.command('[con_id=%s] swap container with con_id %d' % (
                        window.id, targetWindow.id))
                else:
                    # can't find a good position for it let i3 handler
                    pass

                self.i3.command('[con_id=%s] focus' % (window.id))
        pass

    def on_move(self, event):
        swallow = self.swallowDict.get(str(event.container.id))
        if swallow != None:
            focusWindow = self.i3.get_tree().find_focused()
            if focusWindow != None:
                mark = "swallow"+str(swallow['id'])
                self.unMarkAllNode(focusWindow.root(), mark)
                self.i3.command('[con_id=%s] mark --add %s' %
                                (focusWindow.parent.id, mark))
                swallow["layout"] = focusWindow.layout
                swallow["index"] = focusWindow.parent.nodes.index(focusWindow)
                swallow["parent_nodes"] = len(focusWindow.parent.nodes)
                swallow["isMaster"] = self.checkNodeIsMater(focusWindow)
                pass

    def on_binding(self, event):

        pass

    def on_focus(self, event):

        pass

    def on_tick(self, event):
        args = event.payload.split(' ')
        if(len(args) == 2 and args[0] == 'swallow'):
            try:
                self.nextSwallowId = int(args[1], 16)
            except Exception as e:
                print("id not valid %s" % args[1])
        pass 
