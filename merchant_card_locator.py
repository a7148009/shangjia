"""
商家卡片精确定位器
用于准确识别高德地图搜索结果页面中的商家卡片，并计算安全点击位置

核心功能：
1. 多层过滤验证（Y轴、宽度、高度、关键词）
2. 安全点击区域计算（避开按钮区域）
3. 置信度评分系统
4. 可配置参数支持
5. 调试模式支持
"""
import re
from typing import List, Dict, Optional
from lxml import etree
import yaml


class MerchantCardLocator:
    """商家卡片定位器"""

    def __init__(self, screen_width: int, screen_height: int, config_path: str = "config.yaml"):
        """
        初始化定位器

        Args:
            screen_width: 屏幕宽度（像素）
            screen_height: 屏幕高度（像素）
            config_path: 配置文件路径
        """
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 加载配置参数
        self.params = self._load_config(config_path)

        # 🆕 将Y轴固定值转换为相对屏幕高度的像素值
        # 商家列表区域：约20%-75%的屏幕高度
        if 'safe_y_min_ratio' in self.params:
            self.params['safe_y_min'] = int(screen_height * self.params['safe_y_min_ratio'])
        if 'safe_y_max_ratio' in self.params:
            self.params['safe_y_max'] = int(screen_height * self.params['safe_y_max_ratio'])

        # 广告关键词列表
        self.ad_keywords = [
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

        # 排除关键词列表
        self.excluded_keywords = [
            '搜索', '导航', '路线', '附近', '更多', '分享', '收藏',
            '大家还在搜', '根据当前位置推荐', '附近更多', '查看',
            '去过', '想去', '人均', '公里', 'km', 'm'
        ]

        # 标签关键词列表（避免将标签当作商家名）
        self.tag_keywords = [
            '收录', '入驻', '营业', '评分', '评价', '超棒',
            '很好', '好', '分', '星', '人去过', '想去', '收藏'
        ]

    def _load_config(self, config_path: str) -> Dict:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            配置参数字典
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('locator_params', self._get_default_params())
        except FileNotFoundError:
            print(f"⚠ 配置文件 {config_path} 不存在，使用默认参数")
            return self._get_default_params()
        except Exception as e:
            print(f"⚠ 加载配置文件失败: {e}，使用默认参数")
            return self._get_default_params()

    def _get_default_params(self) -> Dict:
        """
        获取默认参数

        Returns:
            默认参数字典
        """
        return {
            # 🆕 Y轴范围改用比例（适配不同分辨率）
            'safe_y_min_ratio': 0.20,       # 安全Y轴最小值：20%屏幕高度（过滤顶部搜索栏、广告）
            'safe_y_max_ratio': 0.75,       # 安全Y轴最大值：75%屏幕高度（过滤底部导航栏）
            'safe_y_min': 500,              # 备用：固定像素值（如果没有ratio则使用）
            'safe_y_max': 1800,             # 备用：固定像素值

            # 宽度和高度（保持原有设置）
            'min_width_ratio': 0.60,        # 最小宽度比例（支持多种布局：66%和94%）
            'max_width_ratio': 0.98,        # 最大宽度比例
            'min_height': 100,              # 最小高度（像素）
            'max_height': 450,              # 最大高度（像素，支持带图片的商家卡片）

            # 点击区域（已经是比例，无需修改）
            'click_zone_left_ratio': 0.1,   # 安全点击区域左边界比例
            'click_zone_right_ratio': 0.6,  # 安全点击区域右边界比例（避开右侧按钮）
            'click_zone_top_ratio': 0.3,    # 安全点击区域顶部比例
            'click_zone_bottom_ratio': 0.7  # 安全点击区域底部比例
        }

    def find_merchant_cards(self, xml_content: str, debug_mode: bool = False) -> List[Dict]:
        """
        从UI层级XML中查找所有商家卡片

        Args:
            xml_content: UI层级XML内容
            debug_mode: 是否启用调试模式

        Returns:
            商家卡片列表，每个卡片包含：
            - name: 商家名称
            - bounds: 边界坐标 {'x1', 'y1', 'x2', 'y2', 'width', 'height'}
            - click_point: 安全点击坐标 {'x', 'y'}
            - confidence: 置信度（0-1）
            - index: 索引位置
        """
        if not xml_content:
            if debug_mode:
                print("✗ XML内容为空")
            return []

        try:
            # 解析XML
            root = etree.fromstring(xml_content.encode('utf-8'))

            # 策略1：从RecyclerView中查找（主要方法）
            recyclerview_cards = self._extract_from_recyclerview(root, debug_mode)

            # 策略2：从content-desc属性查找（备用方法）
            contentdesc_cards = self._extract_from_contentdesc(root, debug_mode)

            # 合并去重
            all_cards = self._merge_cards(recyclerview_cards, contentdesc_cards)

            # 按Y坐标排序并添加索引
            all_cards.sort(key=lambda c: c['bounds']['y1'])
            for idx, card in enumerate(all_cards):
                card['index'] = idx

            if debug_mode:
                print(f"\n✓ 共识别 {len(all_cards)} 个商家卡片")
                for card in all_cards:
                    self._print_card_info(card)

            return all_cards

        except Exception as e:
            if debug_mode:
                print(f"✗ 解析XML失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_from_recyclerview(self, root, debug_mode: bool = False) -> List[Dict]:
        """
        从RecyclerView结构中提取商家卡片

        Args:
            root: XML根节点
            debug_mode: 是否启用调试模式

        Returns:
            商家卡片列表
        """
        cards = []

        # 查找RecyclerView节点
        recyclerviews = root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')

        if debug_mode:
            print(f"\n🔍 策略1: 从RecyclerView查找")
            print(f"   找到 {len(recyclerviews)} 个RecyclerView")

        for recyclerview in recyclerviews:
            # 查找其下的ViewGroup节点
            viewgroups = recyclerview.xpath('.//node[@class="android.view.ViewGroup" and @clickable="true" and @bounds]')

            if debug_mode:
                print(f"   RecyclerView下有 {len(viewgroups)} 个可点击ViewGroup")

            for idx, viewgroup in enumerate(viewgroups):
                card = self._parse_single_card(viewgroup, idx, debug_mode)
                if card:
                    cards.append(card)

        return cards

    def _extract_from_contentdesc(self, root, debug_mode: bool = False) -> List[Dict]:
        """
        从content-desc属性提取商家卡片（备用方法）

        Args:
            root: XML根节点
            debug_mode: 是否启用调试模式

        Returns:
            商家卡片列表
        """
        cards = []

        # 查找所有带content-desc且可点击的节点
        nodes = root.xpath('//node[@content-desc and @clickable="true" and @bounds]')

        if debug_mode:
            print(f"\n🔍 策略2: 从content-desc查找")
            print(f"   找到 {len(nodes)} 个带content-desc的可点击节点")

        for idx, node in enumerate(nodes):
            card = self._parse_single_card(node, idx, debug_mode)
            if card:
                cards.append(card)

        return cards

    def _parse_single_card(self, node, index: int, debug_mode: bool = False) -> Optional[Dict]:
        """
        解析单个商家卡片节点

        Args:
            node: XML节点
            index: 节点索引
            debug_mode: 是否启用调试模式

        Returns:
            商家卡片信息字典，如果不是有效商家卡片则返回None
        """
        # 第1步：解析bounds坐标
        bounds_str = node.get('bounds', '')
        bounds = self._parse_bounds(bounds_str)

        if not bounds:
            if debug_mode:
                print(f"   ✗ 节点[{index}] bounds解析失败: {bounds_str}")
            return None

        # 第2步：验证bounds有效性
        validation_result = self._validate_bounds(bounds)
        if not validation_result['valid']:
            if debug_mode:
                print(f"   ✗ 节点[{index}] bounds验证失败: {validation_result['reason']}")
                print(f"      bounds: Y={bounds['y1']}-{bounds['y2']}, W={bounds['width']}, H={bounds['height']}")
            return None

        # 第3步：提取商家名称
        merchant_name = self._extract_merchant_name(node)

        if not merchant_name or merchant_name == "未知商家":
            if debug_mode:
                print(f"   ✗ 节点[{index}] 未能提取商家名称")
            return None

        # 第4步：广告过滤
        if self._is_advertisement(merchant_name):
            if debug_mode:
                print(f"   ✗ 节点[{index}] 跳过广告: {merchant_name}")
            return None

        # 第5步：计算安全点击位置
        click_point = self._calculate_safe_click_point(bounds)

        # 第6步：计算置信度
        confidence = self._calculate_confidence(bounds, merchant_name)

        # 构建卡片信息
        card = {
            'name': merchant_name,
            'bounds': bounds,
            'click_point': click_point,
            'confidence': confidence
        }

        if debug_mode:
            print(f"   ✓ 节点[{index}] 识别成功: {merchant_name}")
            print(f"      置信度: {confidence:.2f}")
            print(f"      bounds: [{bounds['x1']},{bounds['y1']}][{bounds['x2']},{bounds['y2']}]")
            print(f"      点击位置: ({click_point['x']}, {click_point['y']})")

        return card

    def _parse_bounds(self, bounds_str: str) -> Optional[Dict]:
        """
        解析bounds字符串

        Args:
            bounds_str: bounds字符串，格式 "[x1,y1][x2,y2]"

        Returns:
            bounds字典 {'x1', 'y1', 'x2', 'y2', 'width', 'height'}，解析失败返回None
        """
        if not bounds_str:
            return None

        # 匹配格式 [x1,y1][x2,y2]
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

    def _validate_bounds(self, bounds: Dict) -> Dict:
        """
        验证bounds有效性

        Args:
            bounds: bounds字典

        Returns:
            验证结果 {'valid': bool, 'reason': str}
        """
        # 验证Y轴范围（过滤顶部广告和底部元素）
        if bounds['y1'] < self.params['safe_y_min']:
            return {'valid': False, 'reason': f"Y轴位置过高 (Y={bounds['y1']} < {self.params['safe_y_min']})"}

        if bounds['y2'] > self.params['safe_y_max']:
            return {'valid': False, 'reason': f"Y轴位置过低 (Y={bounds['y2']} > {self.params['safe_y_max']})"}

        # 验证宽度比例（商家卡片接近全屏宽度）
        width_ratio = bounds['width'] / self.screen_width
        if width_ratio < self.params['min_width_ratio']:
            return {'valid': False, 'reason': f"宽度比例过小 ({width_ratio:.2f} < {self.params['min_width_ratio']})"}

        if width_ratio > self.params['max_width_ratio']:
            return {'valid': False, 'reason': f"宽度比例过大 ({width_ratio:.2f} > {self.params['max_width_ratio']})"}

        # 验证高度（商家卡片高度在合理范围内）
        if bounds['height'] < self.params['min_height']:
            return {'valid': False, 'reason': f"高度过小 ({bounds['height']} < {self.params['min_height']})"}

        if bounds['height'] > self.params['max_height']:
            return {'valid': False, 'reason': f"高度过大 ({bounds['height']} > {self.params['max_height']})"}

        return {'valid': True, 'reason': ''}

    def _extract_merchant_name(self, node) -> str:
        """
        提取商家名称（2025-01-16完全重构）

        关键特征：
        1. 黑色加粗文字（在卡片顶部）
        2. 长度4-20字符
        3. 不包含【】等商品标识
        4. Y轴位置在卡片上半部分

        Args:
            node: XML节点

        Returns:
            商家名称，未找到返回"未知商家"
        """
        bounds = self._parse_bounds(node.get('bounds', ''))
        if not bounds:
            return "未知商家"

        card_top = bounds['y1']
        card_height = bounds['height']

        # 查找所有文本节点
        text_nodes = node.xpath('.//node[@text and string-length(@text) > 0 and @bounds]')

        candidate_names = []

        for text_node in text_nodes:
            text = text_node.get('text', '').strip()

            # 清理HTML标签
            clean_text = re.sub(r'<[^>]+>', '', text).strip()

            if not clean_text or len(clean_text) < 3:
                continue

            # 关键过滤1：排除商品名特征（包含【】）
            if '【' in clean_text or '】' in clean_text:
                continue  # 商品名通常包含【】

            # 关键过滤2：长度判断（商家名4-30字符）
            if len(clean_text) > 30:
                continue  # 太长，是商品名或描述

            # 关键过滤3：排除商品描述词
            product_keywords = [
                '花束', '鲜花速递', '配送', '上门', '仅限', '不含',
                '指定', '全国', '实体店', '速递', '保证'
            ]
            keyword_count = sum(1 for kw in product_keywords if kw in clean_text)
            if keyword_count >= 3:
                continue  # 包含3个以上商品词，是商品名

            # 关键过滤4：排除地址和距离
            if self._is_address_text(clean_text):
                continue
            if self._is_excluded_text(clean_text):
                continue
            if self._is_tag_text(clean_text):
                continue

            # 关键过滤5：Y轴位置（应该在卡片上半部分）
            text_bounds = self._parse_bounds(text_node.get('bounds', ''))
            if text_bounds:
                text_y = text_bounds['y1']
                relative_y = (text_y - card_top) / card_height if card_height > 0 else 1

                # 商家名通常在卡片前40%的位置
                if relative_y > 0.4:
                    continue

                # 添加到候选名单
                candidate_names.append({
                    'text': clean_text,
                    'length': len(clean_text),
                    'y_pos': text_y,
                    'relative_y': relative_y
                })

        # 选择最合适的商家名
        if not candidate_names:
            return "未知商家"

        # 排序规则：
        # 1. 相对Y轴位置越靠上越好（relative_y越小越好）
        # 2. 长度4-20字符优先
        candidate_names.sort(key=lambda x: (
            x['relative_y'],                         # 相对位置最重要
            abs(x['length'] - 10),                   # 长度接近10最好
            -x['length'] if x['length'] <= 20 else x['length']
        ))

        best_name = candidate_names[0]['text']

        # 最后验证：如果还是太长，截断
        if len(best_name) > 30:
            best_name = best_name[:25]

        return best_name

    def _is_excluded_text(self, text: str) -> bool:
        """
        判断是否是需要排除的文本

        Args:
            text: 文本内容

        Returns:
            是否需要排除
        """
        for keyword in self.excluded_keywords:
            if keyword in text:
                return True
        return False

    def _is_tag_text(self, text: str) -> bool:
        """
        判断是否是标签文本（避免将标签当作商家名）

        Args:
            text: 文本内容

        Returns:
            是否为标签
        """
        # 🆕 关键过滤：排除"收录X年"、"收录X个月"等时间标签
        if re.match(r'^收录\d+[年个月天]', text):
            return True  # 匹配: 收录1年、收录2年、收录6个月

        # 长度过短（<=3字符）的标签
        if len(text) <= 3:
            for keyword in self.tag_keywords:
                if keyword in text:
                    return True

        # 完全匹配标签关键词
        for keyword in ['收录', '入驻商家', '营业中', '评分', '评价']:
            if text == keyword or text.endswith(keyword):
                return True

        return False

    def _is_address_text(self, text: str) -> bool:
        """
        判断是否是地址信息（2025-01-16新增）

        地址特征：
        - 包含区/县/市/省
        - 包含路/街/道/巷/大棚/棚/号
        - 包含距离单位（公里/km/米/m）
        - 包含时间描述（驾车/步行/分钟）

        Args:
            text: 文本内容

        Returns:
            是否为地址信息
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

        # 判断逻辑：
        # 1. 同时包含行政区划 + 道路建筑 → 肯定是地址
        if has_admin and has_road:
            return True

        # 2. 包含距离/时间描述 → 肯定是地址或距离信息
        if has_distance:
            return True

        # 3. 包含"大棚"、"草莓地"等特殊地址词
        if any(keyword in text for keyword in ['大棚', '草莓地', '市场', '交易中心']):
            # 但如果是"XX市场"、"XX交易中心"作为商家名的一部分，需要判断
            # 如果文本很短（<15字符）且只包含一个关键词，可能是商家名
            if len(text) < 15:
                keyword_count = sum(1 for k in ['大棚', '草莓地', '市场', '交易中心'] if k in text)
                if keyword_count == 1 and ('市场' in text or '交易中心' in text):
                    # 可能是"斗南花卉市场"这种商家名
                    return False
            return True

        # 4. 包含地址编号模式（如"A35-38号"、"2期487-488"）
        if re.search(r'[A-Z]\d+-\d+号', text) or re.search(r'\d+期\d+-\d+', text):
            return True

        return False

    def _is_advertisement(self, text: str) -> bool:
        """
        判断是否是广告内容

        Args:
            text: 文本内容

        Returns:
            是否为广告
        """
        # 检查广告关键词
        for keyword in self.ad_keywords:
            if keyword in text:
                return True

        # 排除时间格式（如 "半夜12:12"）
        if re.match(r'.{0,3}\d{1,2}:\d{2}', text):
            return True

        # 排除纯数字加单位（如 "5.8公里"）
        if re.match(r'^\d+\.?\d*\s?(公里|km|米|m|分钟)$', text):
            return True

        return False

    def _calculate_safe_click_point(self, bounds: Dict) -> Dict:
        """
        计算安全点击位置

        商家卡片结构：
        ┌────────────────────────────────────────────────┐
        │ [商家名称]              [收藏] [电话] [导航]  │ ← 顶部区域
        │ 地址: xxx                    距离: 5km       │ ← 中部区域
        │ 评分: 4.9 ★★★★★              [查看详情]      │ ← 底部区域
        └────────────────────────────────────────────────┘
          ↑ 安全点击区域（10%-60%）    ↑ 按钮区域（60%-100%）

        策略：
        - 水平方向：点击左侧10%-60%区域中心（避开右侧按钮）
        - 垂直方向：点击中部30%-70%区域中心（避开顶部和底部）

        Args:
            bounds: bounds字典

        Returns:
            点击坐标 {'x': int, 'y': int}
        """
        # 计算水平安全区域
        safe_left = bounds['x1'] + bounds['width'] * self.params['click_zone_left_ratio']
        safe_right = bounds['x1'] + bounds['width'] * self.params['click_zone_right_ratio']
        click_x = int((safe_left + safe_right) / 2)

        # 计算垂直安全区域
        safe_top = bounds['y1'] + bounds['height'] * self.params['click_zone_top_ratio']
        safe_bottom = bounds['y1'] + bounds['height'] * self.params['click_zone_bottom_ratio']
        click_y = int((safe_top + safe_bottom) / 2)

        return {'x': click_x, 'y': click_y}

    def _calculate_confidence(self, bounds: Dict, name: str) -> float:
        """
        计算置信度

        基于以下因素：
        1. Y轴位置（核心区域600-1500分数最高）
        2. 宽度比例（支持66%和94%两种布局）
        3. 高度范围（150-250像素分数最高）
        4. 名称长度（4-20个字符分数最高）

        Args:
            bounds: bounds字典
            name: 商家名称

        Returns:
            置信度（0-1）
        """
        confidence = 1.0

        # 因素1: Y轴位置评分
        if 600 <= bounds['y1'] <= 1500:
            confidence *= 1.0  # 核心区域
        elif 500 <= bounds['y1'] < 600:
            confidence *= 0.9  # 接近顶部
        elif 1500 < bounds['y1'] <= 1700:
            confidence *= 0.95  # 接近底部
        else:
            confidence *= 0.7  # 边缘区域

        # 因素2: 宽度比例评分（支持两种布局）
        width_ratio = bounds['width'] / self.screen_width

        # 优先布局：全屏宽度（90%-95%）
        if 0.90 <= width_ratio <= 0.95:
            confidence *= 1.0
        elif 0.85 <= width_ratio < 0.90 or 0.95 < width_ratio <= 0.98:
            confidence *= 0.95

        # 次选布局：窄版布局（64%-70%，成都等城市）
        elif 0.64 <= width_ratio <= 0.70:
            confidence *= 0.90  # 稍低置信度，但仍接受
        elif 0.60 <= width_ratio < 0.64:
            confidence *= 0.85  # 边缘宽度
        else:
            confidence *= 0.7  # 其他宽度

        # 因素3: 高度评分（支持纯文本和带图片两种）
        if 150 <= bounds['height'] <= 250:
            confidence *= 1.0  # 标准高度
        elif 100 <= bounds['height'] < 150 or 250 < bounds['height'] <= 300:
            confidence *= 0.95  # 接近标准
        elif 300 < bounds['height'] <= 450:
            confidence *= 0.90  # 带图片的卡片
        else:
            confidence *= 0.8  # 其他高度

        # 因素4: 名称长度评分
        name_len = len(name)
        if 4 <= name_len <= 20:
            confidence *= 1.0
        elif 3 <= name_len < 4 or 20 < name_len <= 30:
            confidence *= 0.9
        elif name_len > 30:
            confidence *= 0.7

        return confidence

    def _merge_cards(self, cards1: List[Dict], cards2: List[Dict]) -> List[Dict]:
        """
        合并两个卡片列表，去除重复项

        去重策略：
        1. 使用Y轴位置 + 商家名称作为唯一标识
        2. 优先选择宽度更大的卡片（置信度更高）

        Args:
            cards1: 卡片列表1（优先级高）
            cards2: 卡片列表2

        Returns:
            合并后的卡片列表
        """
        merged = []
        seen_cards = {}  # key: (y轴, 商家名), value: card

        # 🆕 修复：使用Y轴+名称去重，同一Y轴同名商家只保留一个
        all_cards = cards1 + cards2

        for card in all_cards:
            # 使用Y轴和商家名作为唯一标识
            # Y轴允许10像素误差（同一行）
            y_key = card['bounds']['y1'] // 10 * 10  # 向下取整到10的倍数
            card_key = (y_key, card['name'])

            if card_key not in seen_cards:
                # 第一次看到这个卡片，直接添加
                seen_cards[card_key] = card
            else:
                # 已经有相同位置和名称的卡片，比较宽度
                existing_card = seen_cards[card_key]
                # 优先选择宽度更大的卡片（更完整）
                if card['bounds']['width'] > existing_card['bounds']['width']:
                    seen_cards[card_key] = card

        merged = list(seen_cards.values())
        return merged

    def _print_card_info(self, card: Dict):
        """
        打印卡片详细信息（用于调试）

        Args:
            card: 卡片信息字典
        """
        print(f"\n  [{card.get('index', '?')}] {card['name']}")
        print(f"      Bounds: [{card['bounds']['x1']},{card['bounds']['y1']}][{card['bounds']['x2']},{card['bounds']['y2']}]")
        print(f"      Size: {card['bounds']['width']}x{card['bounds']['height']} (宽x高)")
        print(f"      Click: ({card['click_point']['x']}, {card['click_point']['y']})")
        print(f"      Confidence: {card['confidence']:.2%}")
