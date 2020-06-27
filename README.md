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
    > you don't need to open the first terminal full screen.
    > It will better if the terminal is display floating center on your screen
    > when you open another window it will change to tilling mode .

    ![first terminal display](./screenshot/first_terminal.png)
* swap from any window to master with shorcut `$mod+m`
* move from any window to master with shorcut `$mod+shift+m`

    ![swap master ](./screenshot/swap_master.gif)

* swallow instance 
    > this version is focus on i3 master and it is different to another swallow version 
    > because it will try to restore the original position when you move the swallow instance

    ![swallow vifm](./screenshot/swallow_vifm.gif)
# Dependencies

1. python3
2. [i3ipc-python](https://github.com/altdesktop/i3ipc-python)
3. xdotool
4. xprop
5. xdo


# Install

 Install python 3 and install i3ipc libary

 `pip3 install i3ipc`

## Run from terminal

 download this script and put it to your i3 config folder and run

`chmod +x ./i3_master_layout.py`

`python3 ./i3_master_layout.py`
 
 you can run it use bash file [i3_master](./i3_master)

 `./i3_master`

## Run with i3

 put it to your i3 config

```bash
 exec --no-startup-id python3 $HOME/.config/i3/i3-master-slave/i3-master
 # swap to master node
 bindsym $mod+m nop swap master 
 # go to master node
 bindsym $mod+shift+m nop go master 
 # enable/disable master layout in current workspace
 bindsym $mod+alt+m nop master toggle 

 ```
# Config

open file i3_master_layout and change terminal to your default terminal class `st` or `Alacritty`
Use `xdotool selectwindow getwindowgeometry` to  change size and get a good postion

```python
terminal = 'Alacritty'
screenWidth = 1300
screenHeight = 800
posX = 310
posY = 160
limitWindowOnMaster = 2
isEnableSwallow     = True
isSwapMasterOnNewInstance = True  # new instance on master is change to master

```
# File manager with swallow 

 file manager is not working with the swallow function. You need to add scripts. 
 >Example vifm
 * Copy file [swallow](./swallow) to folder `$HOME/.config/vifm/scripts/`.
 * Edit /vifmrc 
    ```
    filextype *.bmp,*.jpg,*.jpeg,*.png,*.gif,*.xpm
            \ {View in feh}
            \ swallow feh %f,
            \ {View in gpicview}
            \ gpicview %c,
            \ {View in shotwell}
            \ shotwell,
    ```
# TODO

- [x] Swallow on master is bad

- [ ]  Swallow use xprop and xdotool is slow.

