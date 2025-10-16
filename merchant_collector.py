"""
商家信息采集模块
用于从高德地图采集商家信息

核心特性：
1. RecyclerView商家卡片识别（content-desc + clickable + bounds）
2. HTML标签电话号码提取
3. 采集4项核心信息：商家名称、地址、电话号码、顶部截图
4. 精确定位算法（MerchantCardLocator）
5. 点击前后验证机制
6. 调试模式支持
"""
import time
import re
import os
from typing import List, Dict, Optional
from adb_manager import ADBDeviceManager
from lxml import etree
from merchant_card_locator import MerchantCardLocator
from merchant_detail_locator import MerchantDetailLocator
import yaml


class MerchantCollector:
    """商家信息采集类"""

    def __init__(self, adb_manager: ADBDeviceManager, config_path: str = "config.yaml"):
        """
        初始化采集器

        Args:
            adb_manager: ADB设备管理器实例
            config_path: 配置文件路径
        """
        self.adb_manager = adb_manager
        self.collected_merchants = []
        self.last_page_content = None

        # 加载配置
        self.config = self._load_config(config_path)

        # 获取屏幕尺寸
        screen_width, screen_height = self.adb_manager.get_screen_size()

        # 初始化精确定位器
        self.card_locator = MerchantCardLocator(screen_width, screen_height, config_path)
        self.detail_locator = MerchantDetailLocator(screen_width, screen_height)

        # 调试模式设置
        self.debug_mode = self.config.get('debug_mode', {}).get('enabled', False)
        self.screenshot_dir = self.config.get('debug_mode', {}).get('screenshot_dir', './debug_screenshots')

        # 创建截图目录
        if self.debug_mode and self.config.get('debug_mode', {}).get('save_card_screenshots', False):
            os.makedirs(self.screenshot_dir, exist_ok=True)
            print(f"✓ 调试模式已启用，截图将保存至: {self.screenshot_dir}")

    def _load_config(self, config_path: str) -> Dict:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            配置字典
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠ 配置文件 {config_path} 不存在，使用默认配置")
            return {}
        except Exception as e:
            print(f"⚠ 加载配置文件失败: {e}，使用默认配置")
            return {}

    def parse_merchant_list(self) -> List[Dict]:
        """
        解析当前页面的商家列表（使用精确定位器）

        使用 MerchantCardLocator 进行精确识别：
        - 多层过滤验证（Y轴、宽度、高度、关键词）
        - 安全点击区域计算（避开按钮区域）
        - 置信度评分系统
        - 支持调试模式

        Returns:
            商家信息列表，每个包含：
            - name: 商家名称
            - click_x, click_y: 安全点击坐标
            - bounds: 边界坐标字典
            - confidence: 置信度（0-1）
            - index: 在列表中的索引位置
        """
        merchants = []

        try:
            # 获取UI层级
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                print("✗ 无法获取UI层级")
                return merchants

            # 使用精确定位器查找商家卡片
            if self.debug_mode:
                print("\n" + "="*80)
                print("🔍 开始解析商家卡片列表")
                print("="*80)

            cards = self.card_locator.find_merchant_cards(xml_content, debug_mode=self.debug_mode)

            # 转换为旧格式以兼容现有代码
            for card in cards:
                merchant = {
                    'name': card['name'],
                    'click_x': card['click_point']['x'],
                    'click_y': card['click_point']['y'],
                    'bounds': card['bounds'],
                    'confidence': card['confidence'],
                    'index': card.get('index', 0)
                }
                merchants.append(merchant)

            # 调试模式：保存截图
            if self.debug_mode and self.config.get('debug_mode', {}).get('save_card_screenshots', False):
                self._save_cards_screenshot(merchants)

            if self.debug_mode:
                print("="*80)
                print(f"✓ 解析完成，共识别 {len(merchants)} 个商家卡片")
                print("="*80 + "\n")
            else:
                print(f"解析到 {len(merchants)} 个商家")

        except Exception as e:
            print(f"✗ 解析商家列表失败: {e}")
            import traceback
            traceback.print_exc()

        return merchants

    def _save_cards_screenshot(self, merchants: List[Dict]):
        """
        保存商家卡片截图（调试模式）

        Args:
            merchants: 商家信息列表
        """
        try:
            # 获取当前屏幕截图
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(self.screenshot_dir, f"merchant_list_{timestamp}.png")

            # 使用ADB截图
            self.adb_manager.device.screenshot(screenshot_path)
            print(f"  📸 截图已保存: {screenshot_path}")
            print(f"  📋 识别到 {len(merchants)} 个商家卡片")

        except Exception as e:
            print(f"  ⚠ 保存截图失败: {e}")

    def _print_pre_click_verification(self, merchant: Dict, current_idx: int, total: int):
        """
        打印点击前验证信息

        Args:
            merchant: 商家信息字典
            current_idx: 当前索引（1-based）
            total: 总数量
        """
        print(f"\n  {'='*60}")
        print(f"  📍 点击前验证 [{current_idx}/{total}]")
        print(f"  {'='*60}")
        print(f"  商家名称: {merchant['name']}")
        print(f"  点击坐标: ({merchant['click_x']}, {merchant['click_y']})")
        print(f"  卡片边界: [{merchant['bounds']['x1']},{merchant['bounds']['y1']}]"
              f"[{merchant['bounds']['x2']},{merchant['bounds']['y2']}]")
        print(f"  卡片尺寸: {merchant['bounds']['width']}x{merchant['bounds']['height']} 像素")

        if 'confidence' in merchant:
            confidence = merchant['confidence']
            confidence_level = "高" if confidence >= 0.9 else ("中" if confidence >= 0.7 else "低")
            print(f"  置信度: {confidence:.2%} ({confidence_level})")

        print(f"  {'='*60}")

    def _verify_post_click(self) -> bool:
        """
        验证点击后是否进入正确页面

        Returns:
            是否成功进入商家详情页
        """
        print(f"\n  🔍 点击后验证...")

        try:
            # 检查是否进入商家详情页
            if self._is_on_merchant_detail_page():
                print(f"  ✓ 验证通过：成功进入商家详情页")
                return True
            else:
                print(f"  ✗ 验证失败：未进入商家详情页")

                # 调试模式：保存截图
                if self.debug_mode:
                    timestamp = time.strftime('%Y%m%d_%H%M%S')
                    screenshot_path = os.path.join(self.screenshot_dir, f"click_failed_{timestamp}.png")
                    try:
                        self.adb_manager.device.screenshot(screenshot_path)
                        print(f"    📸 错误页面截图已保存: {screenshot_path}")
                    except:
                        pass

                return False

        except Exception as e:
            print(f"  ✗ 验证过程出错: {e}")
            return False

    def _extract_from_recyclerview(self, root, screen_width: int, screen_height: int) -> List[Dict]:
        """
        从RecyclerView结构中提取商家信息（主要方法）

        识别模式：
        //node[@class="androidx.recyclerview.widget.RecyclerView"]
          /node[@class="android.view.ViewGroup" and @clickable="true"]
        """
        merchants = []

        # 查找RecyclerView
        recyclerviews = root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')

        for recyclerview in recyclerviews:
            # 查找其下的ViewGroup节点
            viewgroups = recyclerview.xpath('.//node[@class="android.view.ViewGroup" and @clickable="true" and @bounds]')

            for viewgroup in viewgroups:
                merchant_info = self._parse_merchant_card(viewgroup, screen_width, screen_height)
                if merchant_info:
                    merchants.append(merchant_info)

        return merchants

    def _extract_from_contentdesc(self, root, screen_width: int, screen_height: int) -> List[Dict]:
        """
        从content-desc属性提取商家信息（备用方法）
        """
        merchants = []

        # 查找所有带content-desc且可点击的节点
        nodes = root.xpath('//node[@content-desc and @clickable="true" and @bounds]')

        for node in nodes:
            merchant_info = self._parse_merchant_card(node, screen_width, screen_height)
            if merchant_info:
                merchants.append(merchant_info)

        return merchants

    def _parse_merchant_card(self, node, screen_width: int, screen_height: int) -> Optional[Dict]:
        """
        解析单个商家卡片节点
        """
        # 获取bounds
        bounds = node.get('bounds', '')
        if not bounds:
            return None

        match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if not match:
            return None

        x1, y1, x2, y2 = map(int, match.groups())

        # 严格的Y轴区域过滤（商家列表在屏幕中部）
        # 昆明：真商家从 Y=612 开始，广告在 Y=255-561
        # 成都：真商家从 Y=533 开始
        # 2025-01-16更新：从450提升至500，更严格过滤顶部广告
        if y1 < 500 or y2 > 1000:
            return None

        # 严格的尺寸过滤
        width = x2 - x1
        height = y2 - y1

        # 宽度必须接近全屏（>85%）
        if width < screen_width * 0.85:
            return None

        # 高度在120-250像素之间
        if height < 120 or height > 250:
            return None

        # 提取商家名称
        merchant_name = self._extract_merchant_name(node)
        if not merchant_name or merchant_name == "未知商家":
            return None

        # 排除广告和系统元素
        if self._is_advertisement(merchant_name):
            print(f"  ⚠ 跳过广告: {merchant_name}")
            return None

        # 计算点击中心点
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        return {
            'name': merchant_name,
            'click_x': center_x,
            'click_y': center_y,
            'bounds': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
        }

    def _extract_merchant_name(self, node) -> str:
        """
        提取商家名称（优先content-desc，其次text节点）
        2025-01-16更新：增加地址过滤
        """
        # 优先使用content-desc
        content_desc = node.get('content-desc', '').strip()
        if content_desc and len(content_desc) > 2:
            if not self._is_excluded_text(content_desc) and not self._is_address_text(content_desc):
                return content_desc

        # 备用：查找text节点
        text_nodes = node.xpath('.//node[@text and string-length(@text) > 0]')
        for text_node in text_nodes:
            text = text_node.get('text', '').strip()
            if text and len(text) > 2:
                # 排除系统文本、地址和距离
                if self._is_excluded_text(text) or self._is_address_text(text):
                    continue
                # 排除纯数字和距离文本
                if text.replace('.', '').replace('km', '').replace('m', '').isdigit():
                    continue
                return text

        return "未知商家"

    def _is_address_text(self, text: str) -> bool:
        """
        判断是否是地址信息（2025-01-16新增）
        与merchant_card_locator.py保持一致
        """
        # 地址关键词（行政区划）
        address_keywords_admin = ['区', '县', '市', '省', '镇', '乡', '村']
        # 地址关键词（道路建筑）
        address_keywords_road = ['路', '街', '道', '巷', '弄', '里', '大棚', '棚', '号', '栋', '楼', '层', '室', '幢']
        # 距离和时间关键词
        distance_keywords = ['公里', 'km', '米', 'm', '驾车', '步行', '分钟', '小时']

        # 计数命中的关键词类型
        has_admin = any(keyword in text for keyword in address_keywords_admin)
        has_road = any(keyword in text for keyword in address_keywords_road)
        has_distance = any(keyword in text for keyword in distance_keywords)

        # 1. 同时包含行政区划 + 道路建筑 → 地址
        if has_admin and has_road:
            return True
        # 2. 包含距离/时间描述 → 地址或距离信息
        if has_distance:
            return True
        # 3. 包含特殊地址词
        if any(keyword in text for keyword in ['大棚', '草莓地', '市场', '交易中心']):
            if len(text) < 15:
                keyword_count = sum(1 for k in ['大棚', '草莓地', '市场', '交易中心'] if k in text)
                if keyword_count == 1 and ('市场' in text or '交易中心' in text):
                    return False  # 可能是商家名
            return True
        # 4. 地址编号模式
        if re.search(r'[A-Z]\d+-\d+号', text) or re.search(r'\d+期\d+-\d+', text):
            return True

        return False

    def _merge_merchant_lists(self, list1: List[Dict], list2: List[Dict]) -> List[Dict]:
        """
        合并两个商家列表，去除重复项
        """
        merged = []
        seen_positions = set()

        # 优先添加list1（RecyclerView结果）
        for merchant in list1:
            pos_key = (merchant['bounds']['x1'], merchant['bounds']['y1'])
            if pos_key not in seen_positions:
                merged.append(merchant)
                seen_positions.add(pos_key)

        # 补充list2中的新商家
        for merchant in list2:
            pos_key = (merchant['bounds']['x1'], merchant['bounds']['y1'])
            if pos_key not in seen_positions:
                merged.append(merchant)
                seen_positions.add(pos_key)

        return merged

    def _is_excluded_text(self, text: str) -> bool:
        """
        判断是否是需要排除的文本（如按钮文本、提示文本等）

        Args:
            text: 文本内容

        Returns:
            是否需要排除
        """
        excluded_keywords = [
            '搜索', '导航', '路线', '附近', '更多', '分享', '收藏',
            '大家还在搜', '根据当前位置推荐', '附近更多', '查看',
            '去过', '想去', '人均', '公里', 'km', 'm'
        ]

        for keyword in excluded_keywords:
            if keyword in text:
                return True

        return False

    def _is_advertisement(self, text: str) -> bool:
        """
        识别并排除广告内容

        Args:
            text: 文本内容

        Returns:
            是否为广告
        """
        # 广告关键词（增强版 - 2025-01-16更新）
        ad_keywords = [
            '高德红包', '优惠', '券', '领取', '满减', '折扣', '减',
            '刚刚浏览', '大家还在搜', '推荐', '榜单', '服务推荐',
            '扫街榜', '爆款', '精选', '新客', '满', '已领取',
            '鲜花上门配送', '上门配送', '配送服务', '买花榜',
            '鲜花配送', '送货上门', '配送推荐', '服务', '推荐商家',
            # 强化过滤：组合词
            '场地布置', '气球派对', '开业花篮', '绿植',
            '（昆明店）', '（成都店）', '（西安店）',  # 连锁广告特征
            '馨爱鲜花'  # 明确的广告商家
        ]

        for keyword in ad_keywords:
            if keyword in text:
                return True

        # 排除时间格式（如 "半夜12:12"）
        if re.match(r'.{0,3}\d{1,2}:\d{2}', text):
            return True

        # 排除纯数字加单位（如 "5.8公里"）
        if re.match(r'^\d+\.?\d*\s?(公里|km|米|m|分钟)$', text):
            return True

        return False

    def _find_merchant_name_by_similarity(self, root, expected_name: str, screen_height: int) -> str:
        """
        通过相似度匹配查找商家名（2025-01-16新增）

        策略：在整个XML中搜索与期望名称最相似的文本
        这比固定Y轴搜索更可靠，因为不同城市布局可能不同

        Args:
            root: XML根节点
            expected_name: 期望的商家名（来自卡片）
            screen_height: 屏幕高度

        Returns:
            找到的商家名称
        """
        if not expected_name or expected_name == "未知商家":
            return self._extract_merchant_name_from_detail(root, screen_height)

        # 清理期望名称
        expected_clean = re.sub(r'[（）()·.。\s]', '', expected_name)

        all_text_nodes = root.xpath('//node[@text and string-length(@text) > 0 and @bounds]')

        best_match = None
        best_score = 0

        for node in all_text_nodes:
            text = node.get('text', '').strip()
            clean_text = re.sub(r'<[^>]+>', '', text).strip()

            if len(clean_text) < 3 or len(clean_text) > 50:
                continue

            # 🆕 关键过滤：排除明显不是商家名的文本
            # 排除纯数字评分（如"4.1"、"3.8"）
            if re.match(r'^\d+\.\d+$', clean_text):
                continue
            # 排除时间
            if re.match(r'^\d{2}:\d{2}', clean_text):
                continue
            # 排除照片标签
            if re.match(r'^照片\(\d+\)$', clean_text):
                continue

            # 清理后再比较
            clean_text_compare = re.sub(r'[（）()·.。\s]', '', clean_text)

            # 计算相似度
            if expected_clean in clean_text_compare or clean_text_compare in expected_clean:
                # 包含关系，高分
                score = 1.0
            else:
                # 字符重合度
                common = set(expected_clean) & set(clean_text_compare)
                if len(expected_clean) > 0:
                    score = len(common) / len(expected_clean)
                else:
                    score = 0

            if score > best_score and score >= 0.5:
                best_score = score
                best_match = clean_text  # 保留原始文本（不是clean_text_compare）

        if best_match:
            print(f"✓ 通过相似度匹配找到商家名: {best_match} (相似度: {best_score:.0%})")
            return best_match

        # 如果相似度匹配失败，回退到原方法
        return self._extract_merchant_name_from_detail(root, screen_height)

    def _extract_merchant_name_from_detail(self, root, screen_height: int) -> str:
        """
        从商家详情页提取名称（2025-01-16完全重构）

        策略：
        1. 查找Y轴200-600范围内的最大字体文本
        2. 优先HTML格式<font size="XX">
        3. 必须在页面顶部红框区域内
        4. 排除商品名特征（【】等）

        Args:
            root: XML根节点
            screen_height: 屏幕高度

        Returns:
            商家名称（如未找到返回"未知商家"）
        """
        all_text_nodes = root.xpath('//node[@text and string-length(@text) > 0 and @bounds]')

        candidates = []

        for node in all_text_nodes:
            text = node.get('text', '').strip()
            bounds_str = node.get('bounds', '')

            # 解析bounds
            match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if not match:
                continue

            x1, y1, x2, y2 = map(int, match.groups())

            # 🆕 关键1：Y轴必须在200-1200（扩大范围，包含照片下方的商家名）
            # 商家名通常在照片下方，Y轴可能在600-1000之间
            if not (200 <= y1 <= 1200):
                continue

            # 清理HTML，提取字体大小
            font_size = 0
            clean_text = text

            # 尝试提取HTML font标签
            font_match = re.search(r'<font[^>]*size="(\d+)"[^>]*>([^<]+)</font>', text)
            if font_match:
                font_size = int(font_match.group(1))
                clean_text = font_match.group(2).strip()
            else:
                # 没有HTML标签，直接清理
                clean_text = re.sub(r'<[^>]+>', '', text).strip()

            # 🆕 关键2：长度必须在3-30字符（商家名特征）
            if not (3 <= len(clean_text) <= 30):
                continue

            # 🆕 关键3：排除商品名特征（包含【】）
            if '【' in clean_text or '】' in clean_text:
                continue

            # 🆕 关键4：排除非商家名文本
            if self._is_excluded_text(clean_text):
                continue
            if self._is_address_text(clean_text):
                continue

            # 🆕 关键：排除评分数字（如"3.8"、"4.1"）
            if re.match(r'^\d+\.\d+$', clean_text):
                continue  # 纯数字评分
            if re.match(r'^\d+\.\d+\s*分', clean_text):
                continue  # 带"分"的评分

            # 排除时间（如"09:00"）
            if re.match(r'^\d{2}:\d{2}', clean_text):
                continue

            # 排除营业状态
            if clean_text in ['营业中', '休息中', '即将营业', '已打烊', '暂停营业']:
                continue

            # 排除常见标签和照片标签
            if clean_text in ['入驻商家', '刚刚浏览', '达人笔记', '附近推荐']:
                continue

            # 🆕 排除照片标签（如"照片(1)"、"照片(2)"）
            if re.match(r'^照片\(\d+\)$', clean_text):
                continue
            if clean_text.startswith('照片') or '相册' in clean_text:
                continue

            # 添加到候选
            candidates.append({
                'text': clean_text,
                'font_size': font_size,
                'y_pos': y1,
                'length': len(clean_text)
            })

        if not candidates:
            print("⚠ 未能从详情页提取商家名称")
            return "未知商家"

        # 排序规则（2025-01-16修复）：
        # 1. 字体大小最重要（商家名字体最大）
        # 2. 长度优先（商家名4-20字符）
        # 3. Y轴位置（越靠上越好）
        candidates.sort(key=lambda x: (
            -x['font_size'],                # 字体越大越优先（商家名字体最大）
            abs(x['length'] - 12),          # 长度接近12最好
            x['y_pos']                      # Y轴位置最后考虑
        ))

        best_name = candidates[0]['text']

        # 调试信息：显示前3个候选
        if len(candidates) > 1:
            print(f"  候选商家名Top3:")
            for i, cand in enumerate(candidates[:3]):
                print(f"    [{i+1}] {cand['text']} (字体={cand['font_size']}, Y={cand['y_pos']}, 长度={cand['length']})")

        print(f"✓ 从详情页提取商家名: {best_name} (Y={candidates[0]['y_pos']}, 字体={candidates[0]['font_size']})")

        return best_name

    def _is_on_merchant_detail_page(self) -> bool:
        """
        检测是否在商家详情页（2025-01-16增强：新增右上角3按钮检测）

        商家详情页特征：
        - 【新增】右上角同时包含：搜索按钮 + 反馈按钮 + 更多/关闭按钮
        - 包含"电话"按钮（必须）- 这是有效商家的核心标识
        - 包含"导航"或"路线"按钮
        - 不包含"筛选"、"排序"等列表页标识
        - 排除广告页面（"推荐"、"服务"等）

        页面布局特征：
        ┌─────────────────────────────────┐
        │ [<] 花满庭鲜花  [🔍] [❗] [✕]   │ ← 右上角3个按钮（关键！）
        │                                 │
        │ 📸 [商家照片区域]                │
        │                                 │
        │ 花满庭鲜花（花开相爱旗舰店）    │ ← 商家名称
        │ 四川省成都市金牛区...           │ ← 地址
        │ [电话] [导航] [收藏]            │ ← 操作按钮
        └─────────────────────────────────┘

        Returns:
            是否在商家详情页
        """
        try:
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                return False

            root = etree.fromstring(xml_content.encode('utf-8'))

            # 🆕 关键特征1：右上角3个按钮（搜索、反馈、关闭）
            # 这是商家详情页最显著的特征，位于屏幕顶部右侧
            top_right_nodes = root.xpath('//node[@clickable="true" and @bounds]')
            has_search_btn = False
            has_feedback_btn = False
            has_close_btn = False

            for node in top_right_nodes:
                bounds_str = node.get('bounds', '')
                content_desc = node.get('content-desc', '').strip()
                text = node.get('text', '').strip()

                # 解析坐标
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())

                    # 右上角区域：X > 屏幕宽度的70%, Y < 200
                    screen_width, _ = self.adb_manager.get_screen_size()
                    if x1 > screen_width * 0.7 and y1 < 200:
                        # 检测搜索按钮（放大镜图标）
                        if '搜索' in content_desc or '搜索' in text or 'search' in content_desc.lower():
                            has_search_btn = True
                            if self.debug_mode:
                                print(f"  ✓ 检测到搜索按钮 (X={x1}, Y={y1})")

                        # 检测反馈按钮（感叹号图标）
                        if '反馈' in content_desc or '反馈' in text or '举报' in content_desc or 'feedback' in content_desc.lower():
                            has_feedback_btn = True
                            if self.debug_mode:
                                print(f"  ✓ 检测到反馈按钮 (X={x1}, Y={y1})")

                        # 检测关闭/更多按钮
                        if '关闭' in content_desc or '关闭' in text or '更多' in content_desc or '更多' in text or 'close' in content_desc.lower() or 'more' in content_desc.lower():
                            has_close_btn = True
                            if self.debug_mode:
                                print(f"  ✓ 检测到关闭/更多按钮 (X={x1}, Y={y1})")

            # 右上角3按钮特征（至少2个，因为可能有些按钮识别不到）
            has_top_right_buttons = (has_search_btn and has_feedback_btn) or \
                                   (has_search_btn and has_close_btn) or \
                                   (has_feedback_btn and has_close_btn)

            # 原有特征2：必须有电话按钮（有电话的才是有效商家）
            has_phone = len(root.xpath('//node[contains(@text, "电话") or contains(@content-desc, "电话")]')) > 0

            # 原有特征3：导航按钮
            has_nav = len(root.xpath('//node[contains(@text, "导航") or contains(@content-desc, "导航") or contains(@text, "路线") or contains(@content-desc, "路线")]')) > 0

            # 排除搜索结果页特征
            has_filter = len(root.xpath('//node[contains(@text, "筛选")]')) > 0
            has_sort = len(root.xpath('//node[contains(@text, "排序")]')) > 0

            # 排除广告页面特征
            ad_keywords = ['推荐', '服务推荐', '上门配送', '配送服务']
            is_ad_page = False
            for keyword in ad_keywords:
                if len(root.xpath(f'//node[contains(@text, "{keyword}")]')) > 0:
                    is_ad_page = True
                    break

            # 综合判断（优先级：右上角3按钮 > 电话+导航）
            # 方案1：有右上角3按钮 + 电话按钮（最可靠）
            is_detail_page_v1 = has_top_right_buttons and has_phone
            # 方案2：电话 + 导航（兼容旧版）
            is_detail_page_v2 = has_phone and has_nav and not has_filter and not has_sort

            is_detail_page = (is_detail_page_v1 or is_detail_page_v2) and not is_ad_page

            if is_detail_page:
                if has_top_right_buttons:
                    print("✓ 确认在商家详情页（检测到右上角3按钮）")
                else:
                    print("✓ 确认在商家详情页（检测到电话+导航）")
            else:
                print(f"⚠ 不在商家详情页 (右上角按钮:{has_top_right_buttons}, 电话:{has_phone}, 导航:{has_nav}, 筛选:{has_filter}, 排序:{has_sort}, 广告:{is_ad_page})")

            return is_detail_page

        except Exception as e:
            print(f"页面检测失败: {e}")
            return False

    def _is_on_search_result_page(self) -> bool:
        """
        检测是否在搜索结果页（2025-01-16增强：新增顶部标题检测）

        搜索结果页特征：
        - 【新增】顶部包含"附近上榜"或类似标题文本
        - 包含"筛选"按钮
        - 包含"排序"按钮
        - 包含多个商家卡片（RecyclerView）

        页面布局特征：
        ┌─────────────────────────────────┐
        │ [<] 成都全午区鲜花店  [🔍] [✕]  │ ← 顶部标题栏
        │ 🔥 附近上榜  九里堤附近  ...    │ ← 关键标识！
        │ [筛选] [排序]                   │ ← 关键按钮
        ├─────────────────────────────────┤
        │ [商家卡片1]                     │
        │ [商家卡片2]                     │
        └─────────────────────────────────┘

        Returns:
            是否在搜索结果页
        """
        try:
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                return False

            root = etree.fromstring(xml_content.encode('utf-8'))

            # 🆕 关键特征1：顶部标题区域（Y < 300）包含"附近上榜"等关键词
            # 这是搜索结果页最显著的特征
            top_area_nodes = root.xpath('//node[@text and @bounds]')
            has_top_title = False
            top_title_keywords = ['附近上榜', '榜单', '推荐商家', '附近商家', '搜索结果']

            for node in top_area_nodes:
                bounds_str = node.get('bounds', '')
                text = node.get('text', '').strip()

                # 解析Y轴坐标
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())

                    # 顶部区域：Y < 300
                    if y1 < 300:
                        # 检查是否包含关键词
                        for keyword in top_title_keywords:
                            if keyword in text:
                                has_top_title = True
                                if self.debug_mode:
                                    print(f"  ✓ 检测到顶部标题特征: '{text}' (Y={y1})")
                                break
                        if has_top_title:
                            break

            # 原有特征2：筛选按钮
            has_filter = len(root.xpath('//node[contains(@text, "筛选")]')) > 0

            # 原有特征3：排序按钮
            has_sort = len(root.xpath('//node[contains(@text, "排序")]')) > 0

            # 原有特征4：RecyclerView
            has_recyclerview = len(root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')) > 0

            # 综合判断（优先级：顶部标题 > 筛选/排序）
            # 方案1：有顶部标题 + 筛选按钮（最可靠）
            is_search_page_v1 = has_top_title and has_filter
            # 方案2：筛选 + 排序 + RecyclerView（兼容旧版）
            is_search_page_v2 = has_filter and has_sort and has_recyclerview

            is_search_page = is_search_page_v1 or is_search_page_v2

            if is_search_page:
                if has_top_title:
                    print("✓ 确认在搜索结果页（检测到顶部标题）")
                else:
                    print("✓ 确认在搜索结果页（检测到筛选+排序）")
            else:
                print(f"⚠ 不在搜索结果页 (顶部标题:{has_top_title}, 筛选:{has_filter}, 排序:{has_sort}, RecyclerView:{has_recyclerview})")

            return is_search_page

        except Exception as e:
            print(f"页面检测失败: {e}")
            return False

    def _is_on_dialer_page(self) -> bool:
        """
        检测是否在拨号页面（2025-01-16新增：处理"咨询"按钮特殊情况）

        拨号页面特征：
        - 包含拨号盘（数字按钮0-9）
        - 包含拨号操作元素（如"通话"、"拨号"）
        - 不是高德地图界面（没有商家信息元素）
        - 可能是系统拨号器或第三方通讯APP

        Returns:
            是否在拨号页面
        """
        try:
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                return False

            root = etree.fromstring(xml_content.encode('utf-8'))

            # 特征1：拨号盘数字（检测是否有数字键盘）
            # 拨号盘通常有"1"、"2"、"3"等按钮，content-desc或text包含这些数字
            digit_buttons = root.xpath('//node[@clickable="true" and (@text="1" or @content-desc="1" or @text="2" or @content-desc="2")]')
            has_dialer_digits = len(digit_buttons) > 0

            # 特征2：拨号相关文本
            dialer_keywords = ['拨号', '通话', '呼叫', '联系人', '最近通话', '通讯录']
            has_dialer_text = False
            for keyword in dialer_keywords:
                if len(root.xpath(f'//node[contains(@text, "{keyword}") or contains(@content-desc, "{keyword}")]')) > 0:
                    has_dialer_text = True
                    break

            # 特征3：排除高德地图元素（如果有商家相关元素，说明不是拨号页面）
            amap_keywords = ['商家', '导航', '路线', '地址', '详情']
            has_amap_elements = False
            for keyword in amap_keywords:
                if len(root.xpath(f'//node[contains(@text, "{keyword}")]')) > 0:
                    has_amap_elements = True
                    break

            # 判断：有拨号盘或拨号文本，且没有高德地图元素
            is_dialer = (has_dialer_digits or has_dialer_text) and not has_amap_elements

            if is_dialer:
                print(f"✓ 检测到拨号页面 (拨号盘:{has_dialer_digits}, 拨号文本:{has_dialer_text})")
            else:
                print(f"  不在拨号页面 (拨号盘:{has_dialer_digits}, 拨号文本:{has_dialer_text}, 高德元素:{has_amap_elements})")

            return is_dialer

        except Exception as e:
            print(f"拨号页面检测失败: {e}")
            return False

    def _is_supplement_phone_dialog(self) -> bool:
        """
        检测是否是"补充电话"弹窗（2025-01-16新增：处理商家未留电话的特殊情况）

        补充电话弹窗特征：
        - 包含"补充电话"文本
        - 表示商家未提供电话号码
        - 无法提取电话信息

        Returns:
            是否是补充电话弹窗
        """
        try:
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                return False

            root = etree.fromstring(xml_content.encode('utf-8'))

            # 检测"补充电话"相关文本
            supplement_keywords = ['补充电话', '暂无电话', '未提供电话', '添加电话']
            has_supplement_text = False

            for keyword in supplement_keywords:
                if len(root.xpath(f'//node[contains(@text, "{keyword}") or contains(@content-desc, "{keyword}")]')) > 0:
                    has_supplement_text = True
                    print(f"✓ 检测到补充电话弹窗 (关键词:{keyword})")
                    break

            return has_supplement_text

        except Exception as e:
            print(f"补充电话弹窗检测失败: {e}")
            return False

    def collect_merchant_detail(self, merchant_name: str = None) -> Optional[Dict]:
        """
        采集当前商家详情页的核心信息（2025-01-16重构：使用结构化定位器）

        采集内容（仅4项）：
        1. 商家名称 (name)
        2. 地址 (address)
        3. 电话号码 (phones)
        4. 顶部截图 (image_urls)

        Args:
            merchant_name: 期望的商家名称（用于验证）

        Returns:
            商家详细信息字典，如果商家名不匹配返回None
        """
        merchant_data = {
            'name': '',
            'address': '',
            'phones': [],
            'image_urls': []
        }

        try:
            # 等待页面加载
            time.sleep(2)

            # 获取UI层级
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                print("无法获取商家详情页UI")
                return None

            root = etree.fromstring(xml_content.encode('utf-8'))
            screen_width, screen_height = self.adb_manager.get_screen_size()

            # ========== 🆕 2025-01-16修复：直接使用卡片商家名，不再从详情页提取 ==========
            # 1. 商家名称：直接使用参数传入的商家名（来自卡片列表，最准确）
            merchant_data['name'] = merchant_name
            print(f"✓ 使用卡片商家名: {merchant_name}")

            # 2. 提取地址和电话按钮位置
            # 先尝试用resource-id定位（最可靠）
            detail_info = self._extract_by_resource_id(root)

            if not detail_info['address']:
                # 如果resource-id失败，回退到区域定位
                print("  ⚠ resource-id定位失败，使用区域定位")
                detail_info = self.detail_locator.extract_merchant_info(root, debug_mode=self.debug_mode)

            # 3. 提取地址
            merchant_data['address'] = detail_info['address']

            # 🆕 4. 先检查电话按钮是否存在（2025-01-16优化：先判断后操作）
            phone_button_pos = detail_info['phone_button_pos']

            if not phone_button_pos:
                # ❌ 没有找到电话按钮 → 直接返回None跳过此商家
                print("⚠ 未找到电话按钮，跳过此商家")
                print("  → 立即返回商家列表，不进行后续操作")
                return None

            # ✅ 找到电话按钮 → 继续点击提取电话号码
            print(f"✓ 检测到电话按钮存在，位置: ({phone_button_pos['x']}, {phone_button_pos['y']})")

            # 5. 点击电话按钮获取电话号码
            phones = self._click_and_extract_phone_at_pos(phone_button_pos)

            # 检查是否是咨询按钮（返回None表示跳转到拨号页面）
            if phones is None:
                print("  ⚠ 电话按钮为咨询类型，返回None跳过此商家")
                return None  # 返回None表示需要跳过此商家

            merchant_data['phones'] = phones

            # 5. 截图保存顶部图片区域
            merchant_data['image_urls'] = ['screenshot_0']

            return merchant_data

        except Exception as e:
            print(f"采集商家详情失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_by_resource_id(self, root) -> Dict:
        """
        方案A：使用resource-id精确定位（最可靠的方法）

        高德地图APP的XML结构中，可能包含固定的resource-id：
        - com.autonavi.minimap:id/merchant_title (商家名)
        - com.autonavi.minimap:id/phone_btn (电话按钮)
        - com.autonavi.minimap:id/address_text (地址)
        等等

        Returns:
            信息字典 {name, address, phone_button_pos}
        """
        detail_info = {
            'name': '',
            'address': '',
            'phone_button_pos': None
        }

        try:
            # 查找所有带resource-id的节点
            all_nodes = root.xpath('//node[@resource-id and @bounds]')

            if self.debug_mode:
                print(f"\n  🔍 方案A：搜索resource-id节点")
                print(f"     找到 {len(all_nodes)} 个带resource-id的节点")

            for node in all_nodes:
                resource_id = node.get('resource-id', '')
                text = node.get('text', '').strip()
                content_desc = node.get('content-desc', '').strip()
                bounds_str = node.get('bounds', '')

                # 🆕 关键过滤：排除系统UI元素
                # 排除Android系统UI（如状态栏、导航栏）
                if any(namespace in resource_id for namespace in ['com.android.systemui:', 'android:id/']):
                    continue

                # 清理HTML标签
                clean_text = re.sub(r'<[^>]+>', '', text).strip()

                # 尝试匹配商家名相关的resource-id
                if any(keyword in resource_id.lower() for keyword in ['title', 'name', 'merchant', 'shop']):
                    if clean_text and len(clean_text) >= 3:
                        if not detail_info['name']:
                            # 🆕 排除"收录X年"标签
                            if not re.match(r'^收录\d+[年个月天]', clean_text):
                                detail_info['name'] = clean_text
                                if self.debug_mode:
                                    print(f"     ✓ 商家名: {clean_text} (resource-id={resource_id})")

                # 尝试匹配电话按钮
                if any(keyword in resource_id.lower() for keyword in ['phone', 'tel', 'call']) or \
                   '电话' in clean_text or '电话' in content_desc:
                    if not detail_info['phone_button_pos']:
                        bounds = self._parse_bounds(bounds_str)
                        if bounds:
                            detail_info['phone_button_pos'] = {
                                'x': (bounds['x1'] + bounds['x2']) // 2,
                                'y': (bounds['y1'] + bounds['y2']) // 2
                            }
                            if self.debug_mode:
                                print(f"     ✓ 电话按钮: ({detail_info['phone_button_pos']['x']}, {detail_info['phone_button_pos']['y']}) (resource-id={resource_id})")

                # 尝试匹配地址
                if any(keyword in resource_id.lower() for keyword in ['address', 'location', 'addr']):
                    if clean_text and len(clean_text) > 10:
                        if not detail_info['address']:
                            detail_info['address'] = clean_text
                            if self.debug_mode:
                                print(f"     ✓ 地址: {clean_text} (resource-id={resource_id})")

            # 如果resource-id没找到电话按钮，尝试用文本搜索
            if not detail_info['phone_button_pos']:
                phone_nodes = root.xpath('//node[contains(@text, "电话") or contains(@content-desc, "电话")]')
                if phone_nodes:
                    phone_node = phone_nodes[0]
                    bounds_str = phone_node.get('bounds', '')
                    bounds = self._parse_bounds(bounds_str)
                    if bounds:
                        detail_info['phone_button_pos'] = {
                            'x': (bounds['x1'] + bounds['x2']) // 2,
                            'y': (bounds['y1'] + bounds['y2']) // 2
                        }
                        if self.debug_mode:
                            print(f"     ✓ 电话按钮（文本搜索）: ({detail_info['phone_button_pos']['x']}, {detail_info['phone_button_pos']['y']})")

            # 如果resource-id没找到地址，尝试用关键词搜索
            if not detail_info['address']:
                all_text_nodes = root.xpath('//node[@text and string-length(@text) > 10 and @bounds]')
                for node in all_text_nodes:
                    text = node.get('text', '').strip()
                    clean_text = re.sub(r'<[^>]+>', '', text).strip()

                    # 地址特征：包含区/路/街/号
                    if any(keyword in clean_text for keyword in ['区', '路', '街', '号', '道', '巷']):
                        if len(clean_text) > 10 and len(clean_text) < 100:
                            detail_info['address'] = clean_text
                            if self.debug_mode:
                                print(f"     ✓ 地址（关键词搜索）: {clean_text}")
                            break

        except Exception as e:
            if self.debug_mode:
                print(f"  ✗ resource-id定位失败: {e}")

        return detail_info

    def _parse_bounds(self, bounds_str: str) -> Optional[Dict]:
        """
        解析bounds字符串

        Args:
            bounds_str: bounds字符串，格式 "[x1,y1][x2,y2]"

        Returns:
            bounds字典 {'x1', 'y1', 'x2', 'y2', 'width', 'height'}
        """
        if not bounds_str:
            return None

        match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
        if not match:
            return None

        x1, y1, x2, y2 = map(int, match.groups())

        return {
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
            'width': x2 - x1,
            'height': y2 - y1
        }

    def _click_and_extract_phone_at_pos(self, phone_button_pos: Dict) -> List[str]:
        """
        在指定位置点击电话按钮并提取电话号码（使用精确定位的坐标）

        Args:
            phone_button_pos: 电话按钮位置 {'x': int, 'y': int}

        Returns:
            电话号码列表，如果跳转到拨号页面或无电话则返回None（特殊标记）
        """
        try:
            # 点击电话按钮
            self.adb_manager.click(phone_button_pos['x'], phone_button_pos['y'])
            print(f"✓ 点击电话按钮: ({phone_button_pos['x']}, {phone_button_pos['y']})")
            time.sleep(1.5)

            # 🆕 关键检查1：是否跳转到拨号页面（特殊情况：电话按钮带"咨询"）
            if self._is_on_dialer_page():
                print(f"  ⚠ 检测到拨号页面（电话按钮带'咨询'），无法提取号码")
                print(f"  → 返回商家列表，跳过此商家")
                # 返回None作为特殊标记，表示需要跳过此商家
                self.adb_manager.press_back()
                time.sleep(0.5)
                return None

            # 🆕 关键检查2：是否是"补充电话"弹窗（特殊情况：商家未留电话）
            if self._is_supplement_phone_dialog():
                print(f"  ⚠ 检测到'补充电话'弹窗（商家未留电话）")
                print(f"  → 返回商家列表，跳过此商家")
                # 返回None作为特殊标记，表示需要跳过此商家
                self.adb_manager.press_back()
                time.sleep(0.5)
                return None

            # 提取电话号码
            phones = self._extract_phone_numbers()

            # 关闭电话弹窗
            self.adb_manager.press_back()
            time.sleep(0.5)

            return phones

        except Exception as e:
            print(f"提取电话失败: {e}")
            return []

    def _click_and_extract_phone(self, root, screen_width: int, screen_height: int) -> List[str]:
        """
        点击电话图标并提取电话号码（备用方法，使用搜索）

        Returns:
            电话号码列表，如果跳转到拨号页面则返回None（特殊标记）
        """
        try:
            # 查找电话图标位置
            phone_click_x = int(screen_width * 0.85)
            phone_click_y = int(screen_height * 0.25)

            phone_nodes = root.xpath('//node[contains(@text, "电话") or contains(@content-desc, "电话")]')
            if phone_nodes:
                phone_node = phone_nodes[0]
                bounds = phone_node.get('bounds', '')
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    phone_click_x = (x1 + x2) // 2
                    phone_click_y = (y1 + y2) // 2

            # 点击电话图标
            self.adb_manager.click(phone_click_x, phone_click_y)
            print(f"✓ 点击电话按钮（备用方法）: ({phone_click_x}, {phone_click_y})")
            time.sleep(1.5)

            # 🆕 关键检查1：是否跳转到拨号页面（特殊情况：电话按钮带"咨询"）
            if self._is_on_dialer_page():
                print(f"  ⚠ 检测到拨号页面（电话按钮带'咨询'），无法提取号码")
                print(f"  → 返回商家列表，跳过此商家")
                # 返回None作为特殊标记，表示需要跳过此商家
                self.adb_manager.press_back()
                time.sleep(0.5)
                return None

            # 🆕 关键检查2：是否是"补充电话"弹窗（特殊情况：商家未留电话）
            if self._is_supplement_phone_dialog():
                print(f"  ⚠ 检测到'补充电话'弹窗（商家未留电话）")
                print(f"  → 返回商家列表，跳过此商家")
                # 返回None作为特殊标记，表示需要跳过此商家
                self.adb_manager.press_back()
                time.sleep(0.5)
                return None

            # 提取电话号码
            phones = self._extract_phone_numbers()

            # 关闭电话弹窗
            self.adb_manager.press_back()
            time.sleep(0.5)

            return phones

        except Exception as e:
            print(f"提取电话失败: {e}")
            return []

    def _extract_phone_numbers(self) -> List[str]:
        """
        从电话弹窗中提取电话号码

        三层提取策略：
        1. HTML标签提取：<font size="32px" color="#1A66FF">18685488479</font>
        2. 正则匹配：11位手机号、固定电话等
        3. 全局文本搜索：所有包含数字的文本

        弹窗特征：
        - 标题："拨打电话"
        - 位置：底部 bounds [0,1728][1080,2209]
        - 内容：HTML包裹的电话号码

        Returns:
            电话号码列表
        """
        phones = []

        try:
            time.sleep(1)
            xml_content = self.adb_manager.get_ui_hierarchy()
            if not xml_content:
                return phones

            root = etree.fromstring(xml_content.encode('utf-8'))

            # 策略1：从HTML font标签中提取（最可靠）
            text_nodes = root.xpath('//node[@text and string-length(@text) > 0]')

            for node in text_nodes:
                text = node.get('text', '')

                # 查找HTML font标签
                font_matches = re.findall(r'<font[^>]*>(\d+)</font>', text)
                for phone in font_matches:
                    # 验证是否为有效电话号码
                    if self._is_valid_phone(phone) and phone not in phones:
                        phones.append(phone)
                        print(f"从HTML标签提取到电话: {phone}")

            # 策略2：正则匹配标准格式电话号码
            if not phones:
                for node in text_nodes:
                    text = node.get('text', '')

                    # 匹配电话号码格式（支持多种格式）
                    phone_patterns = [
                        r'1[3-9]\d{9}',  # 11位手机号
                        r'0\d{2,3}-?\d{7,8}',  # 固定电话
                        r'\d{3,4}-\d{7,8}'  # 其他格式
                    ]

                    for pattern in phone_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            # 去除横杠
                            phone = match.replace('-', '')
                            if self._is_valid_phone(phone) and phone not in phones:
                                phones.append(phone)
                                print(f"从正则匹配提取到电话: {phone}")

            # 策略3：验证弹窗标题，确保在正确的对话框中
            dialog_titles = root.xpath('//node[contains(@text, "拨打电话") or contains(@text, "电话")]')
            if not dialog_titles and not phones:
                print("警告：未检测到电话弹窗标题")

        except Exception as e:
            print(f"提取电话号码失败: {e}")
            import traceback
            traceback.print_exc()

        return phones

    def _is_valid_phone(self, phone: str) -> bool:
        """
        验证电话号码是否有效

        Args:
            phone: 电话号码字符串

        Returns:
            是否为有效电话号码
        """
        # 去除非数字字符
        phone_digits = re.sub(r'\D', '', phone)

        # 手机号：11位，1开头
        if len(phone_digits) == 11 and phone_digits.startswith('1'):
            return True

        # 固定电话：7-12位
        if 7 <= len(phone_digits) <= 12:
            return True

        return False

    def _verify_merchant_name_match(self, expected_name: str, actual_name: str) -> bool:
        """
        验证商家名是否匹配（2025-01-16新增）

        Args:
            expected_name: 卡片上的商家名
            actual_name: 详情页的商家名

        Returns:
            是否匹配
        """
        # 清理括号和特殊字符
        expected_clean = re.sub(r'[（）()·.。\s]', '', expected_name)
        actual_clean = re.sub(r'[（）()·.。\s]', '', actual_name)

        # 策略1：完全匹配
        if expected_clean == actual_clean:
            print(f"✓ 商家名完全匹配: {expected_name}")
            return True

        # 策略2：包含关系（期望名是实际名的子集）
        if expected_clean in actual_clean:
            print(f"✓ 商家名包含匹配: 期望'{expected_name}' / 实际'{actual_name}'")
            return True

        # 策略3：字符重合度（至少50%）
        expected_chars = set(expected_clean)
        actual_chars = set(actual_clean)

        if len(expected_chars) == 0:
            return False

        common_chars = expected_chars & actual_chars
        match_ratio = len(common_chars) / len(expected_chars)

        if match_ratio >= 0.5:
            print(f"⚠ 商家名相似度匹配: {match_ratio:.0%} (期望'{expected_name}' / 实际'{actual_name}')")
            return True

        # 不匹配
        print(f"✗ 商家名不匹配！")
        print(f"   期望: {expected_name}")
        print(f"   实际: {actual_name}")
        print(f"   字符重合度: {match_ratio:.0%}")
        return False


    def is_end_of_list(self) -> bool:
        """
        判断是否已到达列表末尾

        Returns:
            是否已到达末尾
        """
        try:
            # 获取当前页面内容
            current_content = self.adb_manager.get_ui_hierarchy()

            if not current_content:
                return False

            # 检查是否有"没有更多了"、"到底了"等提示
            root = etree.fromstring(current_content.encode('utf-8'))
            end_indicators = [
                '没有更多', '已经到底', '没有更多内容', '暂无更多',
                '到底了', '就这些了'
            ]

            text_nodes = root.xpath('//node[@text]')
            for node in text_nodes:
                text = node.get('text', '')
                for indicator in end_indicators:
                    if indicator in text:
                        return True

            # 如果滑动后内容没有变化，也认为到底了
            if self.last_page_content and current_content == self.last_page_content:
                return True

            self.last_page_content = current_content
            return False

        except Exception as e:
            print(f"判断列表结束失败: {e}")
            return False

    def scroll_to_next_page(self):
        """向下滑动到下一页"""
        try:
            width, height = self.adb_manager.get_screen_size()

            # 向上滑动（从下往上）
            self.adb_manager.swipe(
                int(width * 0.5), int(height * 0.8),
                int(width * 0.5), int(height * 0.3),
                0.5
            )
            time.sleep(1)

        except Exception as e:
            print(f"滑动失败: {e}")

    def go_back_to_list(self):
        """
        从商家详情页返回到搜索结果页（智能返回）

        返回策略：
        1. 按返回键
        2. 检查是否回到搜索结果页
        3. 如果返回到了错误页面（如首页），给出警告
        """
        try:
            # 第一次返回
            self.adb_manager.press_back()
            time.sleep(1.5)

            # 检查当前页面
            if self._is_on_search_result_page():
                print("✓ 已返回搜索结果页")
                return True
            elif self._is_on_merchant_detail_page():
                print("⚠ 仍在商家详情页，尝试再次返回")
                # 可能有弹窗，再按一次返回
                self.adb_manager.press_back()
                time.sleep(1.5)

                if self._is_on_search_result_page():
                    print("✓ 已返回搜索结果页")
                    return True
                else:
                    print("✗ 返回失败，可能需要手动干预")
                    return False
            else:
                print("⚠ 返回到了未知页面，可能已回到首页")
                return False

        except Exception as e:
            print(f"返回失败: {e}")
            return False

    def collect_all_merchants_in_category(self, category_name: str, max_merchants: int = 100) -> List[Dict]:
        """
        采集指定分类下的所有商家信息（完整流程控制）

        完整业务流程：
        1. 解析当前页面的商家列表（RecyclerView模式）
        2. 遍历每个商家卡片
        3. 点击进入商家详情页
        4. 提取4项核心信息：商家名称、地址、电话号码、顶部截图
        5. 返回列表页
        6. 滑动到下一页
        7. 重复直到达到最大数量或列表结束

        Args:
            category_name: 分类名称（用于日志）
            max_merchants: 最大采集数量

        Returns:
            采集到的商家信息列表（每项包含4个字段：name, address, phones, image_urls）
        """
        print(f"\n========== 开始采集分类: {category_name} ==========")
        all_merchants = []
        processed_names = set()  # 去重
        page_count = 0
        no_new_merchants_count = 0  # 连续无新商家计数

        try:
            while len(all_merchants) < max_merchants:
                page_count += 1
                print(f"\n--- 第 {page_count} 页 ---")

                # 1. 解析当前页面的商家列表
                merchants_on_page = self.parse_merchant_list()

                if not merchants_on_page:
                    print("当前页面未找到商家，可能已到达列表末尾")
                    break

                print(f"当前页面发现 {len(merchants_on_page)} 个商家")

                # 2. 处理当前页面的每个商家
                new_merchants_count = 0

                for idx, merchant in enumerate(merchants_on_page):
                    merchant_name = merchant['name']

                    # 去重检查
                    if merchant_name in processed_names:
                        print(f"  [{idx+1}/{len(merchants_on_page)}] {merchant_name} - 已处理，跳过")
                        continue

                    print(f"\n  [{idx+1}/{len(merchants_on_page)}] 正在处理: {merchant_name}")

                    try:
                        # ==================== 点击前验证 ====================
                        self._print_pre_click_verification(merchant, idx+1, len(merchants_on_page))

                        # 调试模式：暂停确认
                        if self.debug_mode and self.config.get('debug_mode', {}).get('pause_before_click', False):
                            pause_time = self.config.get('debug_mode', {}).get('pause_duration', 2)
                            print(f"  ⏸ 暂停 {pause_time} 秒以供确认...")
                            time.sleep(pause_time)

                        # 3. 点击商家卡片
                        self.adb_manager.click(merchant['click_x'], merchant['click_y'])

                        # 等待页面加载
                        wait_time = self.config.get('collection', {}).get('wait_after_click', 2.0)
                        time.sleep(wait_time)

                        # ==================== 点击后验证 ====================
                        click_success = self._verify_post_click()

                        if not click_success:
                            print(f"    ✗ 点击后验证失败（可能无电话或是广告页），跳过此商家")
                            self.go_back_to_list()
                            continue

                        # 4. 采集商家详情（4项核心信息）
                        detail_data = self.collect_merchant_detail(merchant_name)

                        # 🆕 检查特殊情况：电话按钮为咨询类型（返回None）
                        if detail_data is None:
                            print(f"    ⚠ 商家电话为咨询类型，跳过此商家")
                            # 不计入采集失败，直接跳过
                            self.go_back_to_list()
                            continue

                        if detail_data:
                            # 合并基本信息和详细信息
                            merchant_full_data = {
                                'name': detail_data.get('name', merchant_name),
                                'address': detail_data.get('address', ''),
                                'phones': detail_data.get('phones', []),
                                'image_urls': detail_data.get('image_urls', []),
                                'category_name': category_name,
                                'collection_time': time.strftime('%Y-%m-%d %H:%M:%S')
                            }

                            all_merchants.append(merchant_full_data)
                            processed_names.add(merchant_name)
                            new_merchants_count += 1

                            print(f"    ✓ 成功采集: {merchant_name}")
                            print(f"      电话: {', '.join(detail_data.get('phones', [])) or 'N/A'}")
                            print(f"      地址: {detail_data.get('address', 'N/A')}")
                        else:
                            print(f"    ✗ 采集失败: {merchant_name}")

                        # 5. 返回列表页
                        self.go_back_to_list()

                        # 6. 检查是否达到最大数量
                        if len(all_merchants) >= max_merchants:
                            print(f"\n已达到最大采集数量: {max_merchants}")
                            break

                    except Exception as e:
                        print(f"    ✗ 处理商家时出错: {e}")
                        # 确保返回列表页
                        self.go_back_to_list()
                        continue

                # 7. 检查是否有新商家
                if new_merchants_count == 0:
                    no_new_merchants_count += 1
                    print(f"\n本页无新商家（连续 {no_new_merchants_count} 页）")

                    if no_new_merchants_count >= 3:
                        print("连续3页无新商家，停止采集")
                        break
                else:
                    no_new_merchants_count = 0

                # 8. 滑动到下一页
                if len(all_merchants) < max_merchants:
                    print("\n滑动到下一页...")
                    self.scroll_to_next_page()

                    # 9. 检查是否到达列表末尾
                    if self.is_end_of_list():
                        print("已到达列表末尾")
                        break

        except Exception as e:
            print(f"\n采集过程出错: {e}")
            import traceback
            traceback.print_exc()

        finally:
            print(f"\n========== 采集完成 ==========")
            print(f"分类: {category_name}")
            print(f"总页数: {page_count}")
            print(f"成功采集: {len(all_merchants)} 个商家")

        return all_merchants

    def collect_single_merchant(self, merchant_index: int = 0) -> Optional[Dict]:
        """
        采集单个商家信息（用于测试）

        Args:
            merchant_index: 商家在当前页面的索引位置

        Returns:
            商家详细信息字典（包含4个核心字段：name, address, phones, image_urls）
        """
        try:
            # 1. 解析当前页面
            merchants = self.parse_merchant_list()

            if not merchants:
                print("未找到商家列表")
                return None

            if merchant_index >= len(merchants):
                print(f"索引超出范围，当前页面共 {len(merchants)} 个商家")
                return None

            merchant = merchants[merchant_index]
            print(f"准备采集: {merchant['name']}")

            # 2. 点击商家
            self.adb_manager.click(merchant['click_x'], merchant['click_y'])
            time.sleep(2)

            # 3. 采集详情（4项核心信息）
            detail_data = self.collect_merchant_detail(merchant['name'])

            # 4. 返回列表
            self.go_back_to_list()

            # 🆕 检查特殊情况：电话按钮为咨询类型（返回None）
            if detail_data is None:
                print(f"\n⚠ 商家电话为咨询类型，跳过此商家")
                return None

            if detail_data:
                # 返回4项核心信息
                full_data = {
                    'name': detail_data.get('name', merchant['name']),
                    'address': detail_data.get('address', ''),
                    'phones': detail_data.get('phones', []),
                    'image_urls': detail_data.get('image_urls', []),
                    'collection_time': time.strftime('%Y-%m-%d %H:%M:%S')
                }

                print(f"\n采集结果:")
                print(f"  商家名称: {full_data['name']}")
                print(f"  电话号码: {', '.join(full_data['phones']) or 'N/A'}")
                print(f"  地址: {full_data['address'] or 'N/A'}")
                print(f"  截图: {len(full_data['image_urls'])} 张")

                return full_data

            return None

        except Exception as e:
            print(f"采集单个商家失败: {e}")
            import traceback
            traceback.print_exc()
            return None
