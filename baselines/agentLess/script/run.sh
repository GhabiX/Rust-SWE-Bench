set -ex

# api_key.sh

source script/api_key.sh

export PYTHONPATH=`pwd`
export TARGET_ID=
export NJ=32
export NUM_SETS=2
export NUM_SAMPLES_PER_SET=2
export NUM_REPRODUCTION=0
export FOLDER_NAME=rustbench_o4mini_500 
export SWEBENCH_LANG=rust
export PROJECT_FILE_LOC=structure
export DATASET=local_json
export SPLIT=test

unset https_proxy
unset http_proxy

./script/localization1.1.sh
./script/localization1.2.sh
./script/localization1.3.sh
./script/localization1.4.sh
./script/localization2.1.sh
./script/localization3.1.sh
./script/localization3.2.sh

./script/repair.sh

./script/selection3.1.sh

# #./script/evaluation.sh


#  ./script/selection1.1.sh
#  ./script/selection1.2.sh
#  ./script/selection1.3.sh
#  ./script/selection2.1.sh
# #./script/selection2.2.sh
# #./script/selection2.3.sh
# #./script/selection2.4.sh