#!/bin/bash

# 退出如果发生任何错误
set -e

echo "=== AGM (Antigravity Manager) macOS 编译打包脚本 ==="

# 检查是否安装了 pip3 和 python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3 环境。"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "❌ 错误: 未找到 pip3，请确认 Python 环境完整。"
    exit 1
fi

echo "📦 创建并激活 Python 虚拟环境 (.venv)..."
python3 -m venv .venv
source .venv/bin/activate

echo "📦 正在虚拟环境中安装打包依赖 (PyInstaller)..."
pip install --upgrade pip
pip install pyinstaller

echo "🔨 开始编译打包 AGM..."

# 使用 PyInstaller 打包
pyinstaller --noconfirm \
            --windowed \
            --name "AGManager" \
            ag_manager.py

echo "🧹 退出虚拟环境并清理..."
deactivate
rm -rf build/
rm -rf AGManager.spec

echo "✅ 编译完成！"
echo "📦 正在自动将应用安装到 /Applications (应用程序) 文件夹中..."

APP_NAME="AGManager.app"
TARGET_DIR="/Applications"

# 如果应用程序文件夹已存在旧版，则先删除再覆盖
if [ -d "${TARGET_DIR}/${APP_NAME}" ]; then
    echo "⚠️ 发现已存在的旧版本，正在移除..."
    rm -rf "${TARGET_DIR}/${APP_NAME}"
fi

# 尝试复制包到应用程序目录
cp -R "dist/${APP_NAME}" "${TARGET_DIR}/"

if [ $? -eq 0 ]; then
    echo "✅ 安装成功！"
    echo "🎉 您现在可以直接从 Launchpad (启动台) 或应用程序文件夹打开 AGManager 了！"
else
    echo "❌ 复制到系统目录失败，可能由于权限不足。"
    echo "👉 您的应用已生成在 dist/ 目录下：dist/${APP_NAME}"
    echo "您可以手动将该应用拖入 /Applications (应用程序) 文件夹中。"
fi
