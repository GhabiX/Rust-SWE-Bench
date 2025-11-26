#!/bin/bash

# --- 脚本设置 ---

set -euo pipefail

# --- 1. 参数检查与赋值 ---

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "错误：参数数量不正确。" >&2
    echo "用法: $0 <组织名> <仓库名> <PR号> [补丁文件路径]" >&2
    exit 1
fi

ORG_NAME="$1"
REPO_NAME="$2"
PR_NUMBER="$3"

# --- 2. 准备工作目录 ---


SOURCE_DIR="/home/${REPO_NAME}"
# /workspace 是容器内的工作目录，一般是项目的根目录
DEST_DIR="/workspace/${ORG_NAME}__${REPO_NAME}__0.1" 
REPRODUCER_FILES="/home/reproduce_files" 

if [ ! -d "${SOURCE_DIR}" ]; then
    echo "错误：源目录不存在: ${SOURCE_DIR}" >&2
    exit 1
fi

echo "INFO: 正在创建目标目录: ${DEST_DIR}"
# mkdir 通常很安静，无需重定向
mkdir -p "${DEST_DIR}"

echo "INFO: 正在从 ${SOURCE_DIR} 复制文件到 ${DEST_DIR}"
# cp 也通常很安静，除非出错，保留其错误输出有助于调试
cp -r "${SOURCE_DIR}/." "${DEST_DIR}"

# --- 关键修改：处理可选的 patch_path 参数 ---
patch_path="" 
if [ "$#" -eq 4 ]; then
    patch_path="$4"
    echo "INFO: 提供了补丁文件路径: ${patch_path}"
    
    if [ ! -f "${patch_path}" ]; then
        echo "错误：补丁文件不存在: ${patch_path}" >&2
        exit 1
    fi
    echo "INFO: 正在应用补丁: ${patch_path}"
    
    cd "${DEST_DIR}" || exit 1

    git apply -v "${patch_path}"
fi
# --- 关键修改结束 ---


# --- 3. 设置代理和环境 ---
# echo "INFO: 正在设置代理..."
# export https_proxy="http://127.00.1:1081"
# export http_proxy="http://127.0.0.1:1081"

echo "INFO: 正在准备环境脚本 (输出将被隐藏)..."
# chmod 本身无输出，无需修改
chmod +x "${REPRODUCER_FILES}/env.sh"

# set -x 仍然会打印出这行命令本身
bash "${REPRODUCER_FILES}/env.sh" > /dev/null 2>&1


# --- 4. 运行主程序 ---

VENV_PATH="/workspace/rta-venv/bin/activate" 
if [ -f "${VENV_PATH}" ]; then
    echo "INFO: 正在激活 Python 虚拟环境..."
    source "${VENV_PATH}"
else
    echo "警告：虚拟环境未找到: ${VENV_PATH}" >&2
fi

echo "INFO: 准备执行主程序 (只显示此步骤的输出)..."
# **关键**：保持这行不变，不进行任何重定向

export RUSTFLAGS="-A warnings"
python3 "${REPRODUCER_FILES}/main.py" "${ORG_NAME}" "${REPO_NAME}" "${PR_NUMBER}"