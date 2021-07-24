#!/bin/bash
# use dmenu to excute command because perfomance of rofi
# use need to patch dmenu with center and border with patch
dmenuCommand="dmenu -i -bw 2 -l 10 -fn 'Hack' -p '' -c "
# dmenuCommand="dmenu -i -l 10 -fn 'Hack' -p '✟' "
command="./rofi-ag.sh | ${dmenuCommand}" 
status="2" 
result=" "


DIR=`dirname $0`
TMP_DIR="/tmp/rofi/${USER}/"
TMP_DIR="/tmp/rofi/${USER}/"
HIST_FILE="${TMP_DIR}history.txt"


if [ ! -d "${TMP_DIR}" ]
then
	mkdir -p "${TMP_DIR}";
fi

while [[  "$result" != "exit" && ! -z "$result" ]] 
do
    agresult=$( eval "$DIR/rofi-ag.sh $result" )
    status=$?
    # echo "STATUS: ${status}"   
    if [[ "${status}" != "1" ]]; then
        result=$(eval "cat $HIST_FILE | ${dmenuCommand} ")
        if [[ ! -z "${result}" ]]; then
            printf -v result "%q\n" "$result"
        else
            result="exit"
        fi
    else
        result="exit"
    fi
done

# echo "done"
