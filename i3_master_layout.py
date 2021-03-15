#!/usr/bin/env python3
# ---------------------------------------

import argparse
import configparser
import os
import shutil
import subprocess
from pprint import pprint
from time import sleep

import i3ipc

import i3_swallow

rootMark = "root"
masterMark = "master"
slaveMark = "slave"


class I3MasterConfig(object):
    def __init__(self):
        self.terminal = 'Alacritty'
        self.screenWidth = 1300
        self.screenHeight = 800
        self.posX = 310
        self.posY = 160
        self.firstScreenPercent = 14  # different size between master and slave (unit : ppt)
        self.limitWindowOnMaster = 2
        self.isEnableSwallow = True
        self.isSwapMasterOnNewInstance = True  # new instance on master is change to master
    pass


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
    pass
    pprint(workspace)
    pprint(result)


class WorkspaceData(object):
    def __init__(self, num: int):
        self.num = num
        self.swapNodeId = 0
        self.masterWidth = 0
        self.firstWindowId = 0
        self.callback = None
        self.isSwallowNext = False
        self.isDisable = False
        self.slaveMark = slaveMark+"_"+str(num)
        self.masterMark = masterMark+"_"+str(num)
        self.rootMark = rootMark+"_"+str(num)
        pass


class I3MasterLayout(object):

    def __init__(self, i3: i3ipc.Con, config: I3MasterConfig, debug=False):
        self.i3 = i3
        self.masterWidth = 0
        self.config=config
        self.debug = debug
        self.callbacks = {}
        self.workSpaceDatas = {}
        self.isSwapMasterOnNewInstance = self.config.isSwapMasterOnNewInstance
        self.isSwallowNext = False
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

    def getWorkSpaceData(self, workspaceNum) -> WorkspaceData:
        ws = self.workSpaceDatas.get(workspaceNum)
        if ws == None:
            ws = WorkspaceData(workspaceNum)
            self.workSpaceDatas[workspaceNum] = ws
        return ws

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
        for child in node.nodes:
            if(mark in child.marks):
                return child
            else:
                result = self.findChildNodeByMarked(child, mark)
                if result != None:
                    return result
        return None

    def findChildNodeById(self, node, conId) -> i3ipc.Con:
        for child in node:
            if child.id == conId :
                return child
            elif child.nodes != None:
                result = self.findChildNodeById(child.nodes, conId)
                if result != None:
                    return result
        return None

    def validateMasterAndSlaveNode(self, workspace):
        root = workspace
        if(root.layout == 'splitv'):
            self.i3.command('[con_id=%s] layout splith' % root.id)

        masterNode = None
        slaveNode = None
        workspaceData = self.getWorkSpaceData(workspace.num)
        masterNode = self.findChildNodeByMarked(root, workspaceData.masterMark)

        if(masterNode != None and len(root.nodes) == 1):
            # check length root.nodes ==1 because i3 will merge the master node to another node
            # then we need to find a better master node from root nodes
            root = masterNode.parent
        elif (len(root.nodes) > 0):
            masterNode = root.nodes[0]
        if(len(root.nodes) > 1):
            # check if have slave node in current root
            for node in root.nodes:
                if workspaceData.slaveMark in node.marks:
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
                                    (masterNode.id, workspaceData.masterMark))
                root = masterNode.parent
                masterNode = allChild[0]
                self.i3.command('[con_id=%s] mark %s' %
                                (masterNode.id, workspaceData.masterMark))
                self.i3.command('[con_id=%s] mark %s' %
                                (root.id, workspaceData.rootMark))
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

            if not workspaceData.masterMark in masterNode.marks:
                self.i3.command('[con_id=%s] mark %s' %
                                (masterNode.id, workspaceData.masterMark))
            if not workspaceData.masterMark in root.marks:
                self.i3.command('[con_id=%s] mark %s' %
                                (root.id, workspaceData.rootMark))
            # check child of masterNode when master is not widow
            if(masterNode.window == None):
                allChild = self.getAllChildWindow(masterNode)
                if(
                    len(allChild) > self.config.limitWindowOnMaster and
                    slaveNode != None
                ):
                    # remove all child node on master if have too many
                    for node in allChild[self.config.limitWindowOnMaster:]:
                        if(node.window != None):
                            self.i3.command('[con_id=%s] move window to mark %s' % (
                                node.id, workspaceData.slaveMark))
                            self.i3.command('[con_id=%s] focus' % (node.id))
                    pass

        if(slaveNode != None and masterNode != None):
            # mark slave
            if not workspaceData.slaveMark in slaveNode.marks:
                self.i3.command('[con_id=%s] mark %s' %
                                (slaveNode.id, workspaceData.slaveMark))
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
                                           workspaceData.slaveMark))
                        if(node.window != None):
                            self.i3.command('[con_id=%s] focus' % (node.id))

        self.getMasterSize()
        pass

    def on_new(self, event):
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceData = self.getWorkSpaceData(workspace.num)
        if workspaceData.isDisable:
            return
        window = self.i3.get_tree().find_focused()

        # print("NEW ===============")
        # pprint(vars(workspaceData))
        # print(window.parent.ipc_data)
        # dumpWorkSpace(workspace.ipc_data)
        if (
            len(workspace.nodes) == 1 and
            len(workspace.nodes[0].nodes) == 0 and
            window.name == self.config.terminal and
            len(workspace.floating_nodes) == 0
        ):
            workspaceData.masterWidth = 0
            workspaceData.firstWindowId = window.id
            event.container.command('floating enable')
            event.container.command(
                "exec xdotool windowsize %d %s %s;exec xdotool windowmove %d %s %s"
                % (window.window, self.config.screenWidth, self.config.screenHeight, window.window, self.config.posX, self.config.posY))

        if (
            workspaceData.firstWindowId != 0 and
            window.floating == "auto_off" and
            len(workspace.floating_nodes) >= 1 and
            len(workspace.floating_nodes[0].nodes) >= 1 and
            len(workspace.nodes) == 1 and
            len(workspace.nodes[0].nodes) == 0
        ):
            # if seconde node open it change first node to tiling mode
            firstNode = self.findChildNodeById(
                workspace.floating_nodes, workspaceData.firstWindowId)
            if(
                firstNode != None and
                firstNode.id != window.id and
                ## only auto change on terminal instance
                firstNode.ipc_data["window_properties"]["instance"] == self.config.terminal
            ):
                firstWindowId = firstNode.id
                self.i3.command('[con_id=%s] floating disable' % firstWindowId)
                self.i3.command('[con_id=%s] move left' % firstWindowId)
                self.i3.command('[con_id=%s] mark %s' % (
                    firstWindowId, self.getWorkSpaceMark(masterMark, workspace.num)))
                if (self.config.firstScreenPercent > 0):
                    self.i3.command('[con_id=%s] resize grow width %s px or %s ppt '
                                    % (firstWindowId, self.config.firstScreenPercent, self.config.firstScreenPercent))
                event.container.command('split vertical')
                workspaceData.firstWindowId = 0
                pass

            if(self.isSwapMasterOnNewInstance):
                self.i3.command('[con_id=%s] mark %s' %
                                (window.parent.id, workspaceData.rootMark))
                self.swapMaster(event)
            pass
        # second node is automatic split vertical
        elif (
            len(window.parent.nodes) == 2 and
            window.parent.layout == 'splith' and
            workspaceData.rootMark not in window.parent.marks
        ):
            event.container.command('split vertical')
            pass

        # swap master and push master to top of stack of slave nodes
        if self.isSwapMasterOnNewInstance:
            isRootParent=  workspaceData.rootMark in window.parent.marks
            masterNode = self.findChildNodeByMarked(
                workspace, workspaceData.masterMark)
            if self.isSwallowNext:
                self.isSwallowNext = False
                if(masterNode!=None):
                    print("resizeMaster")
                    self.resizeMaster(masterNode.id)
                isRootParent = False
                pass
            if(isRootParent):
                slaveNode = self.findChildNodeByMarked(
                    workspace, workspaceData.slaveMark)
                if(masterNode != None and masterNode.id != window.id):
                    if(slaveNode != None and len(slaveNode.nodes)>0):
                        # push to slave stack
                        firstNode = slaveNode.nodes[0]
                        self.i3.command('[con_id=%s] focus' %
                                        (firstNode.id))
                        self.i3.command('[con_id=%s] move window to mark %s' % (
                            masterNode.id, workspaceData.slaveMark))
                        self.i3.command('[con_id=%s] swap container with con_id %d'
                                        % (masterNode.id, firstNode.id))
                        pass
                    else:
                        # no slave stack
                        self.i3.command('[con_id=%s] mark %s' %
                                    (masterNode.id, workspaceData.slaveMark))
                        if len(window.parent.nodes)>0:
                            self.i3.command('[con_id=%s] swap container with con_id %d'
                                            % (masterNode.id, window.id))
                            self.i3.command('[con_id=%s] move left'% ( window.id))


                    self.i3.command('[con_id=%s] unmark %s' %
                                    (masterNode.id, workspaceData.masterMark))
                    self.i3.command('[con_id=%s] mark %s' %
                                    (window.id, workspaceData.masterMark))
                    if(workspaceData.masterWidth != 0):
                        self.i3.command('[con_id=%s] resize set %s 0'
                                        % (window.id, workspaceData.masterWidth))
                    self.i3.command('[con_id=%s] focus' % (masterNode.id))
                    self.i3.command('[con_id=%s] focus' % (window.id))
                    workspaceData.swapNodeId = masterNode.id
                pass
                return
            pass

        self.validateMasterAndSlaveNode(workspace)
    pass

    def gotoMaster(self, event):
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceData = self.getWorkSpaceData(workspace.num)
        masterNode = self.findChildNodeByMarked(
            workspace, workspaceData.masterMark)
        if(masterNode != None):
            lastSwapNodeId = workspaceData.swapNodeId
            if(lastSwapNodeId != 0):
                isInMaster = masterNode.window != None and (
                    workspaceData.masterMark in window.marks)
                if(isInMaster == False):
                    childs = self.getAllChildWindow(masterNode)
                    for node in childs:
                        if(window.id == node.id):
                            isInMaster = True
                            break
                pass
                if(isInMaster):
                    self.i3.command('[con_id=%s] focus' %
                                    (lastSwapNodeId))
                    workspace.swapNodeId = 0
                    return
            pass
            if(masterNode.window != None):
                self.i3.command('[con_id=%s] focus' % (masterNode.id))
                workspaceData.swapNodeId = window.id
            pass
            if(len(masterNode.nodes) > 0 and masterNode.nodes[0].window != None):
                self.i3.command('[con_id=%s] focus' % (masterNode.nodes[0].id))
                workspaceData.swapNodeId = window.id
            pass
    pass

    def swap2Node(self, node1Id: int, node2Id: int, workspaceData: WorkspaceData):
        self.i3.command('[con_id=%s] swap container with con_id %s' %
                        (node1Id, node2Id))
        self.i3.command('[con_id=%s] unmark %s' %
                        (node1Id, workspaceData.masterMark))
        self.i3.command('[con_id=%s] mark --add %s' %
                        (node2Id, workspaceData.masterMark))
        self.i3.command('[con_id=%s] focus' % (node2Id))
        workspaceData.swapNodeId = node1Id
        self.emmit('master_change', node2Id)

    def swapMaster(self, event):
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceData = self.getWorkSpaceData(workspace.num)
        masterNode = self.findChildNodeByMarked(
            workspace, workspaceData.masterMark)
        if(masterNode != None):
            lastSwapNodeId = workspaceData.swapNodeId
            if(self.config.limitWindowOnMaster == 1 or len(masterNode.nodes) == 0):
                if(lastSwapNodeId != 0 and workspaceData.masterMark in window.marks):
                    self.swap2Node(
                        masterNode.id, lastSwapNodeId, workspaceData)
                    pass
                else:
                    self.swap2Node(masterNode.id, window.id,
                                   workspaceData)
            else:
                # multi child in master
                childs = self.getAllChildWindow(masterNode)
                isInMaster = False
                for node in childs:
                    if(window.id == node.id):
                        isInMaster = True
                        break
                if(isInMaster):
                    if(lastSwapNodeId != 0):
                        self.swap2Node(
                            window.id, lastSwapNodeId, workspaceData)
                        # workspaceData.swapNodeId = 0
                    else:
                        for node in childs:
                            if(node.id != window.id):
                                self.swap2Node(
                                    window.id, node.id, workspaceData)
                                break
                else:
                    if(len(childs) > 0 and childs[0].window != None):
                        masterNode = childs[0]
                        pass
                    self.swap2Node(masterNode.id, window.id, workspaceData)

        pass

    def getMasterSize(self):
        window = self.i3.get_tree().find_focused()
        workspace = window.workspace()
        workspaceData = self.getWorkSpaceData(workspace.num)
        if (
            workspaceData.masterMark in window.marks and
            workspaceData.rootMark in window.parent.marks and
            len(window.parent.nodes) == 2
        ):
            workspaceData.masterWidth = int(window.rect.width)
        pass

    def resizeMaster(self, condId: int):
        window = self.i3.get_tree().find_focused()
        workspace = window.workspace()
        workspaceData = self.getWorkSpaceData(workspace.num)
        if(workspaceData.masterWidth>0):
            self.i3.command('[con_id=%s] resize set %s 0'
                            % (condId, workspaceData.masterWidth))
        pass
    # region Event Handler
    def on(self, event_name, callback):
        if self.callbacks is None:
            self.callbacks = {}

        if event_name not in self.callbacks:
            self.callbacks[event_name] = [callback]
        else:
            self.callbacks[event_name].append(callback)

    def emmit(self, event_name, data=None):
        if self.callbacks is not None and event_name in self.callbacks:
            for callback in self.callbacks[event_name]:
                callback(data)
    # endregion

    def on_close(self, event):
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceData = self.getWorkSpaceData(workspace.num)
        if(workspaceData.isDisable):
            return
        allChild=workspace.leaves()
        isCloseMaster = False
        if(workspaceData.masterMark in event.container.marks):
            isCloseMaster = True
        self.validateMasterAndSlaveNode(workspace)
        if(isCloseMaster):
            focusWindow = self.i3.get_tree().find_focused()
            if(focusWindow != None and focusWindow.window != None):
                self.i3.command('[con_id=%s] move left' % (focusWindow.id))
                self.i3.command('[con_id=%s] mark %s' %
                                (focusWindow.id, workspaceData.masterMark))
                if(workspaceData.masterWidth != 0):
                    self.i3.command('[con_id=%s] resize set %s 0'
                                    % (focusWindow.id, workspaceData.masterWidth))
            else:
                print("focus window null")

        if(len(allChild)==1):
            self.i3.command('[con_id=%s] mark %s' % (allChild[0].id,workspaceData.masterMark))
            self.i3.command('[con_id=%s] mark %s' % (allChild[0].parent.id,workspaceData.rootMark))

        pass

    def on_move(self, event):
        pass

    def on_binding(self, event):
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceData= self.getWorkSpaceData(workspace.num)
        command = event.ipc_data["binding"]["command"].strip()
        if(command == "nop swap master"):
            self.swapMaster(event)
        elif(command == "nop master toggle"):
            workspaceData.isDisable = not workspaceData.isDisable
        elif(command == "nop go master"):
            self.gotoMaster(event)
        elif("resize" in event.ipc_data["binding"]["command"]):
            self.getMasterSize()
        elif(self.debug):
            if event.ipc_data["binding"]["command"] == "nop debug":
                workspace = i3.get_tree().find_focused().workspace()
                dumpWorkSpace(workspace.ipc_data)

        if(workspaceData.isDisable):
            return
        self.validateMasterAndSlaveNode(workspace)
        pass

    pass

    def on_tick(self, event):

        self

    def on_focus(self, event):

        self

# End class


i3 = i3ipc.Connection()

listHandler = []
masterConfig= I3MasterConfig()


def on_close(self, event):
    for handler in (listHandler):
        handler.on_close(event)
    pass

def on_floating (self,event):
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
    global masterConfig
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Print debug messages to stderr'
    )
    args = parser.parse_args()

    masterHander = I3MasterLayout(i3, masterConfig, args.debug)
    swallowHander = i3_swallow.I3Swallow(
        i3, masterConfig.isEnableSwallow, masterMark, masterHander)
    if(masterConfig.isEnableSwallow):
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

def readConfig():
    config_path = '%s/.config/i3/i3_master.ini' % os.environ['HOME']
    dir = os.path.dirname(os.path.realpath(__file__))
    if not os.path.isfile(config_path):
        print("No config file in.")
        # copy file
        shutil.copy(dir+"/i3_master.ini", config_path)
        pass
    config = configparser.ConfigParser()
    config.read(config_path)
    global masterConfig
    configData = config['config']
    if(configData!=None):
        masterConfig.terminal = configData.get(
            'terminal', fallback=masterConfig.terminal)
        masterConfig.posX = configData.getint(
            'posX', fallback=masterConfig.posX)
        masterConfig.posY = configData.getint(
            'posY', fallback=masterConfig.posY)
        masterConfig.screenWidth = configData.getint(
            'screenWidth', fallback=masterConfig.screenWidth)
        masterConfig.screenHeight = configData.getint(
            'screenHeight', fallback=masterConfig.screenHeight)
        masterConfig.isEnableSwallow = configData.getboolean(
            'swallow', fallback=masterConfig.isEnableSwallow)
        masterConfig.isSwapMasterOnNewInstance = configData.getboolean(
            'slaveStack', fallback=masterConfig.isEnableSwallow)
        masterConfig.firstScreenPercent = configData.getint(
            'masterSizePlus', fallback=14)
        masterConfig.limitWindowOnMaster = configData.get(
            'limitWindowOnMaster', fallback=masterConfig.limitWindowOnMaster)
    pass

if __name__ == "__main__":
    readConfig()
    main()
