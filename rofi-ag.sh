#!/bin/bash
# use AG search with rofi

#------------ CONFIG ----------------#

SEARCH_DIRECTORY="$HOME/Desktop"
FOLDER_DISPLAY=(
    "~/Downloads"
    "~/Documents"
)

OPENER=xdg-open
TERM_EMU=alacritty
TEXT_EDITOR=nvim
FILE_MANAGER="$HOME/.config/vifm/scripts/vifmrun "

#------------ CONFIG ----------------#


MY_PATH="$(dirname "${0}")"
AG_TEXT_QUERY="--column --noheading --follow --depth 5"
AG_FILE_QUERY='-g "" --follow' 

TMP_DIR="/tmp/rofi/${USER}/"
HIST_FILE="${TMP_DIR}/history.txt"

 VIM_OPEN_EXT=(
"html"
"md"
"py"
"go"
"rb"
"php"
"lua"
"sh"
"cs"
"txt"
"ts"
"js"
"jsx"
)



if [ ! -d "${TMP_DIR}" ]
then
	mkdir -p "${TMP_DIR}";
fi

# Create hist file if it doesn't exist
if [ ! -f "${HIST_FILE}" ]
then
	touch "${HIST_FILE}"
fi
function mExit(){
    exec 1>&-
    exit;
}

function searchAgText(){
    isValid=0
    query="ag $@ $AG_TEXT_QUERY $SEARCH_DIRECTORY "
    if [[ ${#query} -ge 3 ]]; then
        mapfile -t AG_RESULT < <(eval $query)
        index=1
        cat /dev/null > $HIST_FILE
        for s in "${AG_RESULT[@]}"; do 
            if [[  ${#s} -ge 4  ]]; then
                printf -v j "%02d" $index
                COMMAND="$j:${s//$SEARCH_DIRECTORY/''}:t"
                echo $COMMAND >> $HIST_FILE
                echo $COMMAND
                index=$((index + 1))
                isValid=1
            fi
        done
    fi
    
    if [[ isValid == 0 ]]; then
        echo "Notfind, Quit"
        return 1
    else
        return 0
    fi
}
function searchAgFile(){
    query="find $SEARCH_DIRECTORY "
    mapfile -t AG_RESULT < <(eval $query)
    index=1
    cat /dev/null > $HIST_FILE
    for folder in  "${FOLDER_DISPLAY[@]}"; do
        printf -v j "%02d" $index
        COMMAND="$j:${folder}:a"
        echo $COMMAND >> $HIST_FILE
        echo $COMMAND
        index=$((index + 1))
    done
    for s in "${AG_RESULT[@]}"; do
        if [[  ${#s} -ge ${#SEARCH_DIRECTORY}+3  ]]; then
            printf -v j "%02d" $index
            COMMAND="$j:${s//$SEARCH_DIRECTORY/''}:f"
            echo $COMMAND >> $HIST_FILE
            echo $COMMAND
            index=$((index + 1))
        fi
    done
}

function checkNumber(){
    re='^[0-9]+$'
    if ! [[ $@ =~ $re ]] ; then
        return 1
    fi
    return 0
}

function excute(){
    readarray -t ARR < $HIST_FILE 
    for s in "${ARR[@]}"; do 
        if [[ "$1" == "${s:0:2}" ]]; then
            if [[ "$2" == "t" ]]; then
                IFS=':' read -r -a array <<< "$s"
                file=${array[1]}
                line=${array[2]}
                column=${array[3]}
                checkNumber $column
                isLineNumber=$?
                coproc (eval "$TERM_EMU -e $TEXT_EDITOR \"+normal ${line}G${column}|\" $SEARCH_DIRECTORY${file} " > /dev/null 2>&1 )
                mExit
            elif [[ "$2" == "f" ]]; then
                IFS=':' read -r -a array <<< "$s"
                fileOpen $SEARCH_DIRECTORY${array[1]} 
            elif [[ "$2" == "a" ]]; then
                IFS=':' read -r -a array <<< "$s"
                fileOpen ${array[1]} 
            else
                echo "not action"
                echo "quit"
            fi
        fi
    done
}

function fileOpen(){
    file=$@
    filename="${file##*/}"
    extension="${filename##*.}"
    if [[ "$filename" == "$extension" ]]; then
        coproc (eval "$TERM_EMU -e $FILE_MANAGER ${file} " > /dev/null 2>&1 )
        mExit
    elif [[ " ${VIM_OPEN_EXT[@]} " =~ " ${extension} " ]]; then
        coproc ( eval "$TERM_EMU -e $TEXT_EDITOR ${file} " > /dev/null 2>&1 )
        mExit 
    else
        coproc (eval "$OPENER ${file} " > /dev/null 2>&1 )
        mExit
    fi
}


if [ -z $@ ]; then
    searchAgFile ""
elif [[ "$@" == "quit" ]]; then
    exit 0
elif [ "$@" == "--testt" ]
then
    echo "Search text"
    read query
    searchAgText $query
    read query
    ./rofi-ag.sh $query 
elif [ "$@" == "--testf" ]
then
    echo "Search file"
    searchAgFile  ""
    read query
    ./rofi-ag.sh $query 
else
    query=$@
    COMMAND=${query:0:3}
    last=${COMMAND:2:1}
    action="${query: -1}" 
    if [[ $last == ":" ]]; then
        excute "${COMMAND:0:2}" $action
    else
        searchAgText "$@"
    fi
fi

