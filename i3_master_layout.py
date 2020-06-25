#!/usr/bin/env python3
# ---------------------------------------

import i3ipc
import argparse
import subprocess
from pprint import pprint
from time import sleep
import i3_swallow

# change terminal variable to your default terminal and set your terminal startup position

terminal = 'Alacritty'
screenWidth = 1300
screenHeight = 800
posX = 310
posY = 160
firstScreenPercent = 14  # different size between master and slave (unit : ppt)
limitWindowOnMaster = 2
isEnableSwallow = True
isSwapMasterOnNewInstance = True  # new instance on master is change to master


rootMark = "root"
masterMark = "master"
slaveMark = "slave"


def dumpNode(node):
    result = {}
    result["type"] = node["type"]
    result["window"] = node["window"]
    result["layout"] = node["layout"]
    result["percent"] = node["percent"]
    result["nodes"] = []
    if(node.get('marks') != None):
        result['marks'] = node['marks']
    if node.get("window_properties") != None:
        result["title"] = node["window_properties"]["instance"] + \
            " - " + node["window_properties"]["title"]
    if len(node["nodes"]) > 0:
        result["nodes"] = []
        for node in node["nodes"]:
            result["nodes"].append(dumpNode(node))
    if(len(node["floating_nodes"]) > 0):
        result["floating_nodes"] = []
        for node in node["floating_nodes"]:
            result["floating_nodes"].append(dumpNode(node))

    return result


def dumpWorkSpace(workspace: i3ipc.Con):
    result = {}
    result["types"] = workspace["type"]
    result["workspace_layout"] = workspace["workspace_layout"]
    if len(workspace["nodes"]) >= 0:
        result["nodes"] = []
        for node in workspace["nodes"]:
            result["nodes"].append(dumpNode(node))
            pass
    if len(workspace["floating_nodes"]) >= 0:
        result["floating_nodes"] = []
        for node in workspace["floating_nodes"]:
            result["floating_nodes"].append(dumpNode(node))
            pass
    pprint(workspace)
    pprint(result)


class I3MasterLayout(object):

    def __init__(self, i3: i3ipc.Con, debug=False):
        self.i3 = i3
        self.masterWidth = 0
        self.isDisable = False
        self.debug = debug
        self.lastSwapNodeId = 0
        self.lastJumpNodeId = 0
        self.firstConIds = {}
        self.callbacks = {}
        self.isSwapMasterOnNewInstance = isSwapMasterOnNewInstance
        pass

    def unMarkMasterNode(self, node):
        for mark in node.marks:
            if mark == masterMark:
                self.i3.command('[con_id=%s] unmark' % (node.id))
                return True
        for node in node.nodes:
            if(self.unMarkMasterNode(node)):
                return True
        return False

    def getWorkSpaceMark(self, markName, workspaceName):
        return markName+"_"+str(workspaceName)

    def findNextNodeToMaser(self, node):
        if(node.window != None):
            return node
        for node in node.nodes:
            if(node.window != None):
                return node
            else:
                result = self.findNextNodeToMaser(node)
                if result != None:
                    return result
        return None

    def getAllChildWindow(self, root):
        result = []
        for node in root.nodes:
            if(node.window != None):
                result.append(node)
            else:
                result = result + self.getAllChildWindow(node)
        return result

    def findChildNodeByMarked(self, node, mark) -> i3ipc.Con:
        for node in node.nodes:
            if(mark in node.marks):
                return node
            else:
                result = self.findChildNodeByMarked(node, mark)
                if result != None:
                    return result
        return None

    def validateMasterAndSlaveNode(self, workspace):
        root = workspace
        if(root.layout == 'splitv'):
            self.i3.command('[con_id=%s] layout splith' % root.id)

        masterNode = None
        slaveNode = None
        workspaceMasterMark = self.getWorkSpaceMark(masterMark, workspace.num)
        workspaceSlaveMark = self.getWorkSpaceMark(slaveMark, workspace.num)
        workspaceRootMark = self.getWorkSpaceMark(rootMark,workspace.num)
        masterNode = self.findChildNodeByMarked(root, workspaceMasterMark)

        if(masterNode != None and len(root.nodes) == 1):
            # check length root.nodes ==1 because i3 will merge the master node to another node
            # then we need to find a better master node from root nodes
            root = masterNode.parent
        elif (len(root.nodes) > 0):
            masterNode = root.nodes[0]
        if(len(root.nodes) > 1):
            # check if have slave node in current root
            for node in root.nodes:
                if workspaceSlaveMark in node.marks:
                    slaveNode = node
            # if don't have set the second node is slave
            if(slaveNode == None):
                slaveNode = root.nodes[1]

        if(slaveNode == None and masterNode != None):
            # try to find the best solutionn for master and slave node
            # special case i3 will stack slave node into master node in too many connection
            allChild = self.getAllChildWindow(masterNode)

            if(len(allChild) >= 2):
                if(masterNode.id != allChild[0].id):
                    self.i3.command('[con_id=%s] unmark %s' %
                                    (masterNode.id, workspaceMasterMark))
                root = masterNode.parent
                masterNode = allChild[0]
                self.i3.command('[con_id=%s] mark %s' %
                                (masterNode, workspaceMasterMark))
                self.i3.command('[con_id=%s] mark %s' % ( root.id, workspaceRootMark))
                if(len(root.nodes) > 1):
                    slaveNode = root.nodes[1]
                else:
                    # we can't find the best slave node
                    pass

        # check master node
        if(masterNode != None):
            if(root.layout == 'splitv'):
                # if i3 put the master node to child another node we need to move it to parent node
                i3.command('[con_id=%s] move left' % masterNode.id)

            if not workspaceMasterMark in masterNode.marks:
                self.i3.command('[con_id=%s] mark %s' %
                                (masterNode.id, workspaceMasterMark))
            if not workspaceRootMark in root.marks:
                self.i3.command('[con_id=%s] mark %s' % (root.id, workspaceRootMark))
            # check child of masterNode when master is not widow
            if(masterNode.window == None):
                allChild = self.getAllChildWindow(masterNode)
                if(
                    len(allChild) > limitWindowOnMaster and
                    slaveNode != None
                ):
                    # remove all child node on master if have too many
                    for node in allChild[limitWindowOnMaster:]:
                        if(node.window != None):
                            self.i3.command('[con_id=%s] move window to mark %s' % ( node.id, workspaceSlaveMark))
                            self.i3.command('[con_id=%s] focus' % (node.id))
                    pass

        if(slaveNode != None and masterNode != None):
            # mark slave
            if not workspaceSlaveMark in slaveNode.marks:
                self.i3.command('[con_id=%s] mark %s' %
                                (slaveNode.id, workspaceSlaveMark))
            # if(slaveNode.layout=='splitv'):
            #         i3.command('[con_id=%s] layout splith' % slaveNode.id)
            # cleate layout for slave
            if(slaveNode.window != None):
                self.i3.command('[con_id=%s] split vertical' % slaveNode.id)

            if(len(root.nodes) > 2):
                for node in root.nodes:
                    # move all child node from root to slave
                    if node.id != masterNode.id and node.id != slaveNode.id:
                        self.i3.command('[con_id=%s] move %s to mark %s'
                                        % (node.id,
                                           "container" if node.window == None else "window",
                                           self.getWorkSpaceMark(slaveMark, workspace.num)))
                        if(node.window != None):
                            self.i3.command('[con_id=%s] focus' % (node.id))

        self.getMasterSize()
        pass

    def on_new(self, event):
        if self.isDisable:
            return
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        firstWindowId = self.firstConIds.get(workspace.name)
        workspaceRootMark = self.getWorkSpaceMark(rootMark,workspace.num)
        workspaceMasterMark = self.getWorkSpaceMark(masterMark,workspace.num)
        workspaceSlaveMark = self.getWorkSpaceMark(slaveMark,workspace.num)

        # print("NEW ===============")
        # print(window.parent.ipc_data)
        # open first node is floating
        # dumpWorkSpace(workspace.ipc_data)
        if (
            len(workspace.nodes) == 1 and
            len(workspace.nodes[0].nodes) == 0 and
            window.name == terminal and
            len(workspace.floating_nodes) == 0
        ):
            self.firstConIds[workspace.name] = window.id
            event.container.command('floating enable')
            event.container.command(
                "exec xdotool windowsize %d %s %s;exec xdotool windowmove %d %s %s"
                % (window.window, screenWidth, screenHeight, window.window, posX, posY))

        if (
            len(workspace.floating_nodes) == 1 and
            len(workspace.nodes) == 1 and
            firstWindowId != None
        ):
            # if seconde node open it change first node to tiling mode
            del self.firstConIds[workspace.name]
            self.i3.command('[con_id=%s] floating disable' % firstWindowId)
            self.i3.command('[con_id=%s] move left' % firstWindowId)
            self.i3.command('[con_id=%s] mark %s' % (
                firstWindowId, self.getWorkSpaceMark(masterMark, workspace.num)))
            event.container.command('split vertical')
            if (firstScreenPercent > 0):
                self.i3.command('[con_id=%s] resize grow width %s px or %s ppt '
                                % (firstWindowId, firstScreenPercent, firstScreenPercent))
            if(self.isSwapMasterOnNewInstance):
                self.i3.command('[con_id=%s] makr %s' % (window.parent.id,workspaceRootMark))
                self.swapMaster(event)
            pass
        # second node is automatic split vertical
        elif (
            len(window.parent.nodes) == 2 and
            window.parent.layout == 'splith' and
            workspaceRootMark not in window.parent.marks
        ):
            event.container.command('split vertical')
            pass

        # swap master and push master to top of stack of slave nodes
        if(
            self.isSwapMasterOnNewInstance and
           workspaceRootMark in window.parent.marks
        ):
            masterNode = self.findChildNodeByMarked(workspace,workspaceMasterMark)
            slaveNode=self.findChildNodeByMarked(workspace,workspaceSlaveMark)
            if( masterNode != None ):
                if(slaveNode != None):
                    if(len(slaveNode.nodes)>0):
                        firstNode=slaveNode.nodes[0]
                        self.i3.command('[con_id=%s] focus' % (firstNode.id))
                        self.i3.command('[con_id=%s] move window to mark %s' % (masterNode.id, workspaceSlaveMark))
                        self.i3.command('[con_id=%s] swap container with con_id %d'
                                        %  (masterNode.id, firstNode.id))
                        pass
                    self
                self.i3.command('[con_id=%s] unmark %s ' % (masterNode.id, workspaceMasterMark))
                self.i3.command('[con_id=%s] mark --add %s ' % (window.id, workspaceMasterMark))
                self.i3.command('[con_id=%s] focus' % (window.id))
            return

        self.validateMasterAndSlaveNode(workspace)

    pass

    def gotoMaster(self, event):
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        mark = self.getWorkSpaceMark(masterMark, workspace.num)
        masterNode = self.findChildNodeByMarked(workspace, mark)
        if(masterNode != None):
            if(self.lastSwapNodeId != 0):
                isInMaster = masterNode.window != None and (
                    mark in window.marks)
                if(isInMaster == False):
                    childs = self.getAllChildWindow(masterNode)
                    for node in childs:
                        if(window.id == node.id):
                            isInMaster = True
                            break
                pass
                if(isInMaster):
                    self.i3.command('[con_id=%s] focus' %
                                    (self.lastSwapNodeId))
                    self.lastSwapNodeId = 0
                    return
            if(masterNode.window != None):
                self.i3.command('[con_id=%s] focus' % (masterNode.id))
                self.lastSwapNodeId = window.id
            if(len(masterNode.nodes) > 0 and masterNode.nodes[0].window != None):
                self.i3.command('[con_id=%s] focus' % (masterNode.nodes[0].id))
                self.lastSwapNodeId = window.id

            pass
    pass

    def swap2Node(self, node1Id, node2Id, mark):
        self.i3.command('[con_id=%s] swap container with con_id %s' %
                        (node1Id, node2Id))
        self.i3.command('[con_id=%s] unmark %s' % (node1Id, mark))
        self.i3.command('[con_id=%s] mark --add %s' % (node2Id, mark))
        self.emmit('master_change',node2Id)

    def swapMaster(self, event):
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        mark = self.getWorkSpaceMark(masterMark, workspace.num)
        masterNode = self.findChildNodeByMarked(workspace, mark)
        if(masterNode != None):
            if(limitWindowOnMaster == 1 or len(masterNode.nodes) == 0):
                if(self.lastSwapNodeId != 0 and mark in window.marks):
                    self.swap2Node(masterNode.id, self.lastSwapNodeId, mark)
                    self.lastSwapNodeId = 0
                    pass
                else:
                    self.lastSwapNodeId = masterNode.id
                    self.swap2Node(masterNode.id, window.id, mark)
            else:
                # multi child in master
                childs = self.getAllChildWindow(masterNode)
                isInMaster = False
                for node in childs:
                    if(window.id == node.id):
                        isInMaster = True
                        break
                if(isInMaster):
                    if(self.lastSwapNodeId != 0):
                        self.swap2Node(
                            window.id, self.lastSwapNodeId, mark)
                        self.lastSwapNodeId = 0
                    else:
                        for node in childs:
                            if(node.id != window.id):
                                self.swap2Node(window.id, node.id, mark)
                                self.lastSwapNodeId = 0
                                break
                else:
                    if(len(childs) > 0 and childs[0].window != None):
                        masterNode = childs[0]
                        pass
                    self.lastSwapNodeId = masterNode.id
                    self.swap2Node(masterNode.id, window.id, mark)

        pass

    def getMasterSize(self):
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        mark = self.getWorkSpaceMark(masterMark, workspace.num)
        if mark in window.marks:
            if(len(window.parent.nodes) == 2):
                self.masterWidth = window.rect.width
        pass

    # region Event Handler
    def on(self, event_name, callback):
        if self.callbacks is None:
            self.callbacks = {}

        if event_name not in self.callbacks:
            self.callbacks[event_name] = [callback]
        else:
            self.callbacks[event_name].append(callback)

    def emmit(self, event_name,data=None):
        if self.callbacks is not None and event_name in self.callbacks:
            for callback in self.callbacks[event_name]:
                callback(data)
    # endregion

    def on_close(self, event):
        if self.isDisable:
            return
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceMasterMark = self.getWorkSpaceMark(masterMark, workspace.num)
        isCloseMaster = False
        if(workspaceMasterMark in event.container.marks):
            isCloseMaster = True
        self.validateMasterAndSlaveNode(workspace)
        if(isCloseMaster):
            focusWindow = self.i3.get_tree().find_focused()
            if(focusWindow != None and focusWindow.window != None):
                self.i3.command('[con_id=%s] move left' % (focusWindow.id))
                self.i3.command('[con_id=%s] mark %s' %
                                (focusWindow.id, workspaceMasterMark))
                if(self.masterWidth != 0):
                    self.i3.command('[con_id=%s] resize set %s 0'
                                    % (focusWindow.id, self.masterWidth))
            else:
                print("focus window null")
        pass

    def on_move(self, event):
        pass

    def on_binding(self, event):
        workspace = self.i3.get_tree().find_focused().workspace()
        self.validateMasterAndSlaveNode(workspace)
        command = event.ipc_data["binding"]["command"].strip()
        if(command == "nop swap master"):
            self.swapMaster(event)
        elif(command == "nop master toggle"):
            self.isDisable = not self.isDisable
        elif(command == "nop go master"):
            self.gotoMaster(event)
        elif("resize" in event.ipc_data["binding"]["command"]):
            self.getMasterSize()
        elif(self.debug):
            if event.ipc_data["binding"]["command"] == "nop debug":
                workspace = i3.get_tree().find_focused().workspace()
                dumpWorkSpace(workspace.ipc_data)
        pass
    pass

    def on_tick(self, event):

        self

    def on_focus(self, event):

        self

# End class


i3 = i3ipc.Connection()

listHandler = []


def on_close(self, event):
    for handler in (listHandler):
        handler.on_close(event)
    pass


def on_new(self, event):
    for handler in listHandler:
        handler.on_new(event)
    pass


def on_move(self, event):
    for handler in listHandler:
        handler.on_move(event)
    pass

def on_focus(self, event):
    for handler in listHandler:
        handler.on_focus(event)
    pass


def on_binding(self, event):
    for handler in listHandler:
        handler.on_binding(event)
    pass


def on_tick(self, event):
    for handler in listHandler:
        handler.on_tick(event)


def main():
    global listHandler
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Print debug messages to stderr'
    )
    args = parser.parse_args()

    masterHander = I3MasterLayout(i3, args.debug)
    swallowHander = i3_swallow.I3Swallow(i3, terminal, masterMark, masterHander)
    if(isEnableSwallow):
        listHandler.append(swallowHander)
    listHandler.append(masterHander)
    # Subscribe to events

    i3.on("window::new", on_new)
    i3.on("window::focus", on_focus)
    i3.on("window::close", on_close)
    i3.on("window::move", on_move)
    i3.on("binding", on_binding)
    i3.on("tick", on_tick)
    i3.main()


if __name__ == "__main__":
    main()
