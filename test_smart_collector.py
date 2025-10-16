"""
智能采集器测试脚本
演示如何使用新的智能采集流程
"""
import sys
from adb_manager import ADBDeviceManager
from smart_collector import SmartCollector
import json


def main():
    print("="*80)
    print("🧪 智能商家信息采集器 - 测试")
    print("="*80)

    # 第1步：连接设备
    print("\n1️⃣  连接ADB设备...")
    adb = ADBDeviceManager()

    if not adb.connect():
        print("✗ 设备连接失败")
        return

    print(f"✓ 设备已连接: {adb.get_device_info()}")

    # 第2步：获取屏幕分辨率
    screen_info = adb.get_screen_size()
    print(f"✓ 屏幕分辨率: {screen_info['width']}x{screen_info['height']}")

    # 第3步：创建智能采集器
    print("\n2️⃣  初始化智能采集器...")
    collector = SmartCollector(
        adb_manager=adb,
        screen_width=screen_info['width'],
        screen_height=screen_info['height']
    )
    print("✓ 采集器初始化完成")

    # 第4步：执行采集
    print("\n3️⃣  开始采集...")
    print("⚠ 请确保:")
    print("   1. 高德地图已打开")
    print("   2. 已进入搜索结果页（例如搜索'鲜花'）")
    print("   3. 页面显示商家列表")

    input("\n按回车键继续...")

    # 执行采集
    result = collector.collect_from_search_page(debug=True)

    # 第5步：显示结果
    print("\n" + "="*80)
    print("📋 采集结果")
    print("="*80)

    if result['success']:
        print(f"✓ 采集成功")
        print(f"   采集数量: {result['collected_count']}")
        print(f"\n商家列表:")
        for idx, merchant in enumerate(result['data'], 1):
            print(f"\n   [{idx}] {merchant.get('name', 'N/A')}")
            print(f"       电话: {', '.join(merchant.get('phones', ['无']))}")
            print(f"       地址: {merchant.get('address', '无')}")
            if merchant.get('rating'):
                print(f"       评分: {merchant['rating']}分")
            if merchant.get('business_hours'):
                print(f"       营业时间: {merchant['business_hours']}")

        # 保存到文件
        output_file = 'collected_merchants.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result['data'], f, ensure_ascii=False, indent=2)
        print(f"\n✓ 数据已保存到: {output_file}")

    else:
        print(f"✗ 采集失败")
        print(f"   错误: {result.get('error', '未知错误')}")

    print("\n" + "="*80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
