"""
智能商家信息采集器
整合页面状态识别、卡片定位、点击验证、信息提取的完整流程

流程：
1. 页面状态识别 - 确认是搜索结果页且有商家列表
2. 商家卡片定位 - 精确定位每个商家卡片位置
3. 安全点击执行 - 点击商家卡片
4. 结果验证确认 - 验证是否进入正确的详情页
5. 信息提取保存 - 提取商家信息并保存
"""
import time
from typing import Dict, List, Optional
from page_state_analyzer import PageStateAnalyzer
from merchant_card_locator import MerchantCardLocator


class SmartCollector:
    """智能商家信息采集器"""

    def __init__(self, adb_manager, screen_width: int = 1080, screen_height: int = 2340):
        """
        初始化采集器

        Args:
            adb_manager: ADB设备管理器
            screen_width: 屏幕宽度
            screen_height: 屏幕高度
        """
        self.adb = adb_manager
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 初始化组件
        self.page_analyzer = PageStateAnalyzer()
        self.card_locator = MerchantCardLocator(screen_width, screen_height)

        # 采集统计
        self.stats = {
            'total_attempted': 0,      # 尝试采集数
            'success_count': 0,        # 成功采集数
            'failed_count': 0,         # 失败采集数
            'wrong_page_count': 0,     # 点击错误页面数
            'extraction_errors': 0     # 信息提取错误数
        }

    def collect_from_search_page(self, debug: bool = True) -> Dict:
        """
        从搜索结果页采集商家信息

        完整流程：
        1. 验证页面状态
        2. 定位商家卡片
        3. 逐个点击并采集
        4. 返回采集结果

        Args:
            debug: 是否启用调试模式

        Returns:
            采集结果字典
        """
        print("\n" + "="*80)
        print("🚀 开始智能采集流程")
        print("="*80)

        # 第1步：页面状态识别
        xml_content = self._get_ui_hierarchy()
        if not xml_content:
            return self._error_result("无法获取UI层级")

        page_info = self.page_analyzer.analyze_page(xml_content, debug=debug)

        if not page_info['has_merchant_list']:
            print(f"✗ 当前页面不是搜索结果页或没有商家列表")
            print(f"   页面类型: {page_info['page_type']}")
            print(f"   置信度: {page_info['confidence']:.2%}")
            return self._error_result("页面状态不符合要求")

        print(f"✓ 页面状态验证通过")
        print(f"   页面类型: {page_info['page_type']}")
        print(f"   商家数量: {page_info['merchant_count']}")
        print(f"   布局类型: {page_info['layout_type']}")
        print(f"   置信度: {page_info['confidence']:.2%}")

        # 第2步：商家卡片定位
        print(f"\n📍 开始定位商家卡片...")
        merchant_cards = self.card_locator.find_merchant_cards(xml_content, debug_mode=debug)

        if not merchant_cards:
            print(f"✗ 未找到商家卡片")
            return self._error_result("未找到商家卡片")

        print(f"✓ 找到 {len(merchant_cards)} 个商家卡片")

        # 第3步：逐个采集
        collected_data = []
        for idx, card in enumerate(merchant_cards):
            print(f"\n{'─'*80}")
            print(f"📦 采集商家 [{idx+1}/{len(merchant_cards)}]: {card['name']}")
            print(f"{'─'*80}")

            result = self._collect_single_merchant(card, debug=debug)
            if result['success']:
                collected_data.append(result['data'])
                print(f"✓ 采集成功")
            else:
                print(f"✗ 采集失败: {result.get('error', '未知错误')}")

            # 返回搜索结果页
            self._go_back()
            time.sleep(1.5)

        # 输出统计信息
        self._print_statistics()

        return {
            'success': True,
            'page_info': page_info,
            'collected_count': len(collected_data),
            'data': collected_data,
            'statistics': self.stats
        }

    def _collect_single_merchant(self, card: Dict, debug: bool = True) -> Dict:
        """
        采集单个商家信息

        Args:
            card: 商家卡片信息
            debug: 调试模式

        Returns:
            采集结果
        """
        self.stats['total_attempted'] += 1
        merchant_name = card['name']

        # 步骤1：点击卡片
        print(f"   1️⃣  点击商家卡片...")
        print(f"      位置: ({card['click_point']['x']}, {card['click_point']['y']})")
        print(f"      置信度: {card['confidence']:.2%}")

        self._click_point(card['click_point']['x'], card['click_point']['y'])
        time.sleep(2.0)  # 等待页面加载

        # 步骤2：验证是否进入详情页
        print(f"   2️⃣  验证详情页...")
        xml_content = self._get_ui_hierarchy()
        if not xml_content:
            self.stats['failed_count'] += 1
            return {'success': False, 'error': '无法获取详情页UI层级'}

        verify_result = self.page_analyzer.verify_merchant_detail_page(
            xml_content, expected_name=merchant_name
        )

        if not verify_result['is_detail_page']:
            print(f"      ✗ 未进入详情页")
            self.stats['wrong_page_count'] += 1
            return {'success': False, 'error': '未进入详情页'}

        if verify_result['merchant_name'] and not verify_result['match_expected']:
            print(f"      ⚠ 商家名不匹配")
            print(f"         期望: {merchant_name}")
            print(f"         实际: {verify_result['merchant_name']}")

        print(f"      ✓ 已进入详情页")
        print(f"         商家名: {verify_result['merchant_name']}")
        print(f"         有电话: {'是' if verify_result['has_phone'] else '否'}")
        print(f"         有地址: {'是' if verify_result['has_address'] else '否'}")

        # 步骤3：提取信息
        print(f"   3️⃣  提取商家信息...")
        merchant_data = self._extract_merchant_info(xml_content, verify_result)

        if not merchant_data:
            self.stats['extraction_errors'] += 1
            return {'success': False, 'error': '信息提取失败'}

        print(f"      ✓ 信息提取完成")
        print(f"         商家名: {merchant_data.get('name', 'N/A')}")
        print(f"         电话数: {len(merchant_data.get('phones', []))}")
        print(f"         地址: {merchant_data.get('address', 'N/A')[:30]}...")

        self.stats['success_count'] += 1
        return {
            'success': True,
            'data': merchant_data
        }

    def _extract_merchant_info(self, xml_content: str, verify_result: Dict) -> Optional[Dict]:
        """
        提取商家详细信息

        Args:
            xml_content: UI层级XML
            verify_result: 详情页验证结果

        Returns:
            商家信息字典
        """
        try:
            from lxml import etree
            import re

            root = etree.fromstring(xml_content.encode('utf-8'))

            # 提取所有文本
            all_text = []
            for node in root.xpath('//node[@text]'):
                text = node.get('text', '').strip()
                if text:
                    all_text.append(text)

            for node in root.xpath('//node[@content-desc]'):
                desc = node.get('content-desc', '').strip()
                if desc:
                    all_text.append(desc)

            full_text = ' '.join(all_text)

            # 提取电话号码
            phones = list(set(re.findall(r'1[3-9]\d{9}', full_text)))

            # 提取地址（四川省/云南省开头的地址）
            address_patterns = [
                r'(四川省[^，。！？\n]{10,50})',
                r'(云南省[^，。！？\n]{10,50})',
                r'(成都市[^，。！？\n]{10,50})',
                r'(昆明市[^，。！？\n]{10,50})',
            ]

            address = ''
            for pattern in address_patterns:
                match = re.search(pattern, full_text)
                if match:
                    address = match.group(1)
                    break

            # 提取营业时间
            business_hours = ''
            hours_match = re.search(r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})', full_text)
            if hours_match:
                business_hours = hours_match.group(1)

            # 提取评分
            rating = ''
            rating_match = re.search(r'(\d\.\d)\s*分', full_text)
            if rating_match:
                rating = rating_match.group(1)

            return {
                'name': verify_result.get('merchant_name', ''),
                'phones': phones,
                'address': address,
                'business_hours': business_hours,
                'rating': rating,
                'raw_text': full_text[:500]  # 保存原始文本片段
            }

        except Exception as e:
            print(f"      ✗ 提取信息时出错: {e}")
            return None

    def _get_ui_hierarchy(self) -> Optional[str]:
        """获取UI层级XML"""
        try:
            return self.adb.get_ui_hierarchy()
        except Exception as e:
            print(f"✗ 获取UI层级失败: {e}")
            return None

    def _click_point(self, x: int, y: int):
        """点击屏幕坐标"""
        try:
            self.adb.tap(x, y)
        except Exception as e:
            print(f"✗ 点击失败: {e}")

    def _go_back(self):
        """返回上一页"""
        try:
            self.adb.press_key(4)  # KEYCODE_BACK = 4
        except Exception as e:
            print(f"✗ 返回失败: {e}")

    def _error_result(self, error_msg: str) -> Dict:
        """返回错误结果"""
        return {
            'success': False,
            'error': error_msg,
            'statistics': self.stats
        }

    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "="*80)
        print("📊 采集统计")
        print("="*80)
        print(f"尝试采集: {self.stats['total_attempted']}")
        print(f"成功采集: {self.stats['success_count']} ✓")
        print(f"失败采集: {self.stats['failed_count']} ✗")
        print(f"错误页面: {self.stats['wrong_page_count']}")
        print(f"提取错误: {self.stats['extraction_errors']}")
        if self.stats['total_attempted'] > 0:
            success_rate = self.stats['success_count'] / self.stats['total_attempted'] * 100
            print(f"成功率: {success_rate:.1f}%")
        print("="*80 + "\n")
