# FEATURE

 master and slave layout in i3
```
| ------ | ----- |
|        |       |
| Master | Slave |
|        |       |
| ------ | ----- |
```
* open first terminal in floating mode and default position 
* swap from any window to master with shorcut `$mod+m`
* move from any window to master with shorcut `$mod+shift+m`
* swallow instance 

# Dependencies

1. python3
2. [i3ipc-python](https://github.com/altdesktop/i3ipc-python)
3. xdotool
4. xprop


# Install

 Install python 3 and install i3ipc libary

 `pip3 install i3ipc`

 download this script and put it to your i3 config folder and run

`chmod +x $HOME/.config/i3/i3-master-slave/i3_master_layout.py`

`python3 $HOME/.config/i3/i3-master-slave/i3_master_layout.py`

 put it to your i3 config

```bash
 exec --no-startup-id python3 $HOME/.config/i3/i3-master-slave/i3-master-layout.py
 # swap to master node
 bindsym $mod+m nop swap master 
 # go to master node
 bindsym $mod+shift+m nop go master 

 ```
# Config

open file i3_master_layout and change terminal to your default terminal class `st` or `Alacritty`

```python
terminal = 'Alacritty'
screenWidth = 1300
screenHeight = 800
posX = 310
posY = 160
limitWindowOnMaster = 2
isEnableSwallow     = True

```

# TODO

* Swallow on master is bad
* Swallow use xprop and xdotool then it is slow.

