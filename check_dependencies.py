"""
依赖检查脚本
检查所有必需的Python包是否已安装
"""

import sys
import io

# 设置stdout为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_module(module_name, package_name=None):
    """
    检查模块是否可导入

    Args:
        module_name: 模块名
        package_name: pip包名（如果与模块名不同）
    """
    if package_name is None:
        package_name = module_name

    try:
        __import__(module_name)
        print(f"[OK] {module_name:20s} - 已安装")
        return True
    except ImportError:
        print(f"[NO] {module_name:20s} - 未安装 (请运行: pip install {package_name})")
        return False

print("="*60)
print("正在检查依赖包...")
print("="*60)
print()

# 检查所有必需的包
required_modules = [
    ('PyQt6', 'PyQt6'),
    ('uiautomator2', 'uiautomator2'),
    ('lxml', 'lxml'),
    ('yaml', 'pyyaml'),
    ('adbutils', 'adbutils'),
]

all_installed = True
for module_name, package_name in required_modules:
    if not check_module(module_name, package_name):
        all_installed = False

print()
print("="*60)
if all_installed:
    print("[OK] 所有依赖包已安装，程序可以正常运行！")
else:
    print("[NO] 存在未安装的依赖包，请按提示安装")
print("="*60)
print()

# 显示Python版本信息
print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.executable}")
