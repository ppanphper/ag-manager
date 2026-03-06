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
echo "您的应用已生成在 dist/ 目录下："
echo "👉 dist/AGManager.app"
echo ""
echo "双击即可运行！如果要安装到系统，可将其拖入 /Applications (应用程序) 文件夹中。"
