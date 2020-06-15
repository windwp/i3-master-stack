#!/usr/bin/env python3
#---------------------------------------
# This script will make the first window open with terminal is floating and have fixed
# windowsize and position
# When you open a second window it change the first window to normal
# USAGE
# add this script to your i3 config
# exec --no-startup-id python3 $HOME/.config/i3/i3-master-layout.py
# bindsym $mod+m nop swap master
#---------------------------------------

import i3ipc
import argparse
import subprocess
import pprint

from i3_swallow import I3Swallow

# change terminal variable to your default terminal and set your terminal startup position

terminal            = 'Alacritty'
screenWidth         = 1300
screenHeight        = 800
posX                = 310
posY                = 160

firstScreenPercent  = 12  # different size between master and slave (unit : ppt)

limitWindowOnMaster = 2
isEnableSwallow     = True


rootMark            = "root"
masterMark          = "master"
slaveMark           = "slave"


def dumpNode(node):
    result = {}
    result["type"] = node["type"]
    result["window"] = node["window"]
    result["layout"] = node["layout"]
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


def dumpWorkSpace(workspace):
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
    pprint.pprint(workspace)
    pprint.pprint(result)


class I3MasterLayout(object):
    def __init__(self, i3, debug):
        self.i3 = i3
        self.debug = debug
        self.lastSwapNodeId = 0
        self.lastJumpNodeId = 0
        self.firstCondId = {}
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

    def findChildNodeByMarked(self, node, mark):
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
            #if don't have set the second node is slave
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
                self.i3.command('[con_id=%s] mark %s' % (
                    root.id, self.getWorkSpaceMark(rootMark, workspace.num)))
                if(len(root.nodes) > 1):
                    slaveNode = root.nodes[1]
                else:
                    # we can't find the best slave node
                    pass

        #check master node
        if(masterNode != None):
            if(root.layout == 'splitv'):
                # if i3 put the master node to child another node we need to move it to parent node
                i3.command('[con_id=%s] move left' % masterNode.id)

            if not self.getWorkSpaceMark(masterMark, workspace.num) in masterNode.marks:
                self.i3.command('[con_id=%s] mark %s' %
                                (masterNode.id, workspaceMasterMark))
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
                            self.i3.command('[con_id=%s] move window to mark %s' % (
                                node.id, self.getWorkSpaceMark(slaveMark, workspace.num)))
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
                    #move all child node from root to slave
                    if node.id != masterNode.id and node.id != slaveNode.id:
                        self.i3.command('[con_id=%s] move %s to mark %s'
                                        % (node.id,
                                           "container" if node.window == None else "window",
                                           self.getWorkSpaceMark(slaveMark, workspace.num)))
                        if(node.window != None):
                            self.i3.command('[con_id=%s] focus' % (node.id))
        pass

    def on_new(self, event):
        window = self.i3.get_tree().find_focused()
        workspace = self.i3.get_tree().find_focused().workspace()
        firstWindowId = self.firstCondId.get(workspace.name)
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
            self.firstCondId[workspace.name] = window.id
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
            del self.firstCondId[workspace.name]
            self.i3.command('[con_id=%s] floating disable' % firstWindowId)
            self.i3.command('[con_id=%s] move left' % firstWindowId)
            self.i3.command('[con_id=%s] mark %s' % (
                firstWindowId, self.getWorkSpaceMark(masterMark, workspace.num)))
            event.container.command('split vertical')
            if (firstScreenPercent>0):
                self.i3.command('exec sleep 0.5;[con_id=%s] resize grow width %s px or %s ppt '
                                % (firstWindowId,firstScreenPercent,firstScreenPercent ))
            pass
        # second node is automatic split vertical
        elif len(window.parent.nodes) == 2 and window.parent.layout == 'splith':
            event.container.command('split vertical')
            pass

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
        self.i3.command('[con_id=%s] mark %s' % (node2Id, mark))

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

    def on_close(self, event):
        workspace = self.i3.get_tree().find_focused().workspace()
        workspaceMasterMark = self.getWorkSpaceMark(masterMark, workspace.num)
        isCloseMaster = False
        if(workspaceMasterMark in event.container.marks):
            isCloseMaster = True
        self.validateMasterAndSlaveNode(workspace)
        if(isCloseMaster):
            nodeList = self.getAllChildWindow(workspace)
            if(len(nodeList) > 0):
                self.i3.command('[con_id=%s] move left' % (nodeList[0].id))

        pass

    def on_move(self, event):
        pass

    def on_binding(self, event):
        workspace = self.i3.get_tree().find_focused().workspace()
        self.validateMasterAndSlaveNode(workspace)
        if(event.ipc_data["binding"]["command"].strip() == "nop swap master"):
            self.swapMaster(event)
        if(event.ipc_data["binding"]["command"].strip() == "nop go master"):
            self.gotoMaster(event)

        if(self.debug):
            if event.ipc_data["binding"]["command"] == "nop debug":
                workspace = i3.get_tree().find_focused().workspace()
                dumpWorkSpace(workspace.ipc_data)
        pass
    pass

#End class


i3 = i3ipc.Connection()

listHandler = []


def on_close(self, event):
    for handler in reversed(listHandler):
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

def on_binding(self, event):
    for handler in listHandler:
        handler.on_binding(event)
    pass


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
    swallowHander = I3Swallow(i3, terminal)
    if(isEnableSwallow):
        listHandler.append(swallowHander)
    listHandler.append(masterHander)
    # Subscribe to events

    i3.on("window::new", on_new)
    i3.on("window::close", on_close)
    i3.on("window::move", on_move)
    i3.on("binding", on_binding)
    i3.main()


if __name__ == "__main__":
    main()
