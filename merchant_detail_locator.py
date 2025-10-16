"""
商家详情页信息定位器
用于精确提取商家详情页的结构化信息

核心思想：复制商家卡片识别的成功经验
1. 固定的区域划分（Y轴范围）
2. 严格的bounds验证
3. 相对位置计算
4. 多层过滤验证
5. 置信度评分

详情页结构特征（基于红框区域）：
┌────────────────────────────────────────┐
│  [照片区域]  Y=200-600                  │
│  ┌──────────────────────────────────┐  │
│  │ 照片(1)  照片(2)  照片(3)        │  │
│  └──────────────────────────────────┘  │
├────────────────────────────────────────┤
│  [商家名称]  Y=600-800  (最大字体)      │
│   昆明花之源鲜花店                      │
├────────────────────────────────────────┤
│  [红框区域]  Y=800-1200                │
│  📍 4.1分  营业中  10:00-22:00         │
│  📍 官渡区肖家营大棚2期487-488          │
│  📍 [电话] [导航] [分享]               │
└────────────────────────────────────────┘
"""
import re
from typing import Dict, Optional, List
from lxml import etree


class MerchantDetailLocator:
    """商家详情页信息定位器"""

    def __init__(self, screen_width: int, screen_height: int):
        """
        初始化定位器

        Args:
            screen_width: 屏幕宽度（像素）
            screen_height: 屏幕高度（像素）
        """
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 🆕 使用相对比例（百分比），适配不同分辨率
        # 详情页区域划分（基于屏幕高度的百分比）
        self.zone_ratios = {
            'photo_area': {'y_min': 0.08, 'y_max': 0.25},      # 照片区域：8%-25%
            'name_area': {'y_min': 0.25, 'y_max': 0.35},       # 商家名称区域：25%-35%
            'info_area': {'y_min': 0.35, 'y_max': 0.55},       # 红框信息区域：35%-55%（评分、地址、电话）
            'content_area': {'y_min': 0.55, 'y_max': 0.85}     # 内容区域：55%-85%（简介、评论等）
        }

        # 计算实际像素值
        self.zones = {}
        for zone_name, ratios in self.zone_ratios.items():
            self.zones[zone_name] = {
                'y_min': int(screen_height * ratios['y_min']),
                'y_max': int(screen_height * ratios['y_max'])
            }

        print(f"  📱 屏幕尺寸: {screen_width}x{screen_height}")
        print(f"  📐 区域划分（像素）:")
        print(f"     照片区域: Y={self.zones['photo_area']['y_min']}-{self.zones['photo_area']['y_max']}")
        print(f"     商家名区域: Y={self.zones['name_area']['y_min']}-{self.zones['name_area']['y_max']}")
        print(f"     信息区域: Y={self.zones['info_area']['y_min']}-{self.zones['info_area']['y_max']}")

    def extract_merchant_info(self, root, debug_mode: bool = False) -> Dict:
        """
        从详情页提取商家信息（结构化定位）

        策略：
        1. 按区域划分（照片区、商家名区、信息区）
        2. 在每个区域内精确定位
        3. 使用bounds + 相对位置
        4. 多层验证过滤

        Args:
            root: XML根节点
            debug_mode: 是否启用调试模式

        Returns:
            商家信息字典 {name, rating, address, business_hours, phone_button_pos}
        """
        if debug_mode:
            print("\n" + "="*80)
            print("🔍 开始提取商家详情（结构化定位）")
            print("="*80)

        merchant_info = {
            'name': '',
            'rating': '',
            'address': '',
            'business_hours': '',
            'phone_button_pos': None
        }

        try:
            # 1. 提取商家名称（名称区域，Y=600-800）
            merchant_info['name'] = self._extract_name_from_zone(root, debug_mode)

            # 2. 提取红框区域信息（信息区域，Y=800-1200）
            info_data = self._extract_info_from_zone(root, debug_mode)
            merchant_info.update(info_data)

            if debug_mode:
                print("="*80)
                print("✓ 提取完成")
                print(f"  商家名称: {merchant_info['name']}")
                print(f"  评分: {merchant_info['rating']}")
                print(f"  地址: {merchant_info['address']}")
                print(f"  营业时间: {merchant_info['business_hours']}")
                print(f"  电话按钮: {merchant_info['phone_button_pos']}")
                print("="*80 + "\n")

        except Exception as e:
            if debug_mode:
                print(f"✗ 提取失败: {e}")
            import traceback
            traceback.print_exc()

        return merchant_info

    def _extract_name_from_zone(self, root, debug_mode: bool = False) -> str:
        """
        从名称区域提取商家名（Y=600-800）

        关键特征：
        1. 在名称区域内（Y=600-800）
        2. 字体最大（HTML font size）
        3. 长度4-30字符
        4. 不包含【】、照片等标识

        Args:
            root: XML根节点
            debug_mode: 是否启用调试模式

        Returns:
            商家名称
        """
        zone = self.zones['name_area']
        all_text_nodes = root.xpath('//node[@text and string-length(@text) > 0 and @bounds]')

        candidates = []

        for node in all_text_nodes:
            text = node.get('text', '').strip()
            bounds_str = node.get('bounds', '')

            # 解析bounds
            bounds = self._parse_bounds(bounds_str)
            if not bounds:
                continue

            # 关键过滤1：必须在名称区域内
            if not (zone['y_min'] <= bounds['y1'] <= zone['y_max']):
                continue

            # 提取字体大小和清理文本
            font_size = 0
            clean_text = text

            font_match = re.search(r'<font[^>]*size="(\d+)"[^>]*>([^<]+)</font>', text)
            if font_match:
                font_size = int(font_match.group(1))
                clean_text = font_match.group(2).strip()
            else:
                clean_text = re.sub(r'<[^>]+>', '', text).strip()

            # 关键过滤2：长度4-30字符
            if not (4 <= len(clean_text) <= 30):
                continue

            # 关键过滤3：排除非商家名
            if self._is_excluded_name(clean_text):
                continue

            # 添加到候选
            candidates.append({
                'text': clean_text,
                'font_size': font_size,
                'y_pos': bounds['y1'],
                'bounds': bounds
            })

            if debug_mode:
                print(f"  候选商家名: {clean_text} (字体={font_size}, Y={bounds['y1']})")

        if not candidates:
            if debug_mode:
                print("  ⚠ 名称区域未找到商家名")
            return "未知商家"

        # 排序：字体大小优先，Y轴其次
        candidates.sort(key=lambda x: (-x['font_size'], x['y_pos']))

        best_name = candidates[0]['text']

        if debug_mode:
            print(f"  ✓ 识别商家名: {best_name} (字体={candidates[0]['font_size']}, Y={candidates[0]['y_pos']})")

        return best_name

    def _extract_info_from_zone(self, root, debug_mode: bool = False) -> Dict:
        """
        从信息区域提取详细信息（Y=800-1200，红框区域）

        关键特征：
        1. 评分：X.X 分（数字+分）
        2. 营业时间：XX:XX-XX:XX（时间格式）
        3. 地址：包含区/路/街/号，长度>10
        4. 电话按钮：文本包含"电话"

        Args:
            root: XML根节点
            debug_mode: 是否启用调试模式

        Returns:
            信息字典 {rating, address, business_hours, phone_button_pos}
        """
        zone = self.zones['info_area']
        all_text_nodes = root.xpath('//node[@text and string-length(@text) > 0 and @bounds]')

        info_data = {
            'rating': '',
            'address': '',
            'business_hours': '',
            'phone_button_pos': None
        }

        if debug_mode:
            print(f"\n  🔍 扫描信息区域 (Y={zone['y_min']}-{zone['y_max']})")

        for node in all_text_nodes:
            text = node.get('text', '').strip()
            bounds_str = node.get('bounds', '')

            # 解析bounds
            bounds = self._parse_bounds(bounds_str)
            if not bounds:
                continue

            # 关键过滤：必须在信息区域内
            if not (zone['y_min'] <= bounds['y1'] <= zone['y_max']):
                continue

            # 清理HTML
            clean_text = re.sub(r'<[^>]+>', '', text).strip()

            # 1. 提取评分（X.X 分）
            if not info_data['rating']:
                rating_match = re.search(r'(\d+\.\d+)\s*分', clean_text)
                if rating_match:
                    info_data['rating'] = rating_match.group(1)
                    if debug_mode:
                        print(f"    ✓ 评分: {info_data['rating']}分 (Y={bounds['y1']})")

            # 2. 提取营业时间（XX:XX-XX:XX）
            if not info_data['business_hours']:
                time_match = re.search(r'(\d{2}:\d{2}[-~]\d{2}:\d{2})', clean_text)
                if time_match:
                    info_data['business_hours'] = time_match.group(1)
                    if debug_mode:
                        print(f"    ✓ 营业时间: {info_data['business_hours']} (Y={bounds['y1']})")

            # 3. 提取地址（包含区/路/街/号，长度>10）
            if not info_data['address']:
                if any(k in clean_text for k in ['区', '路', '街', '号', '道', '巷']):
                    if len(clean_text) > 10:
                        info_data['address'] = clean_text
                        if debug_mode:
                            print(f"    ✓ 地址: {info_data['address']} (Y={bounds['y1']})")

            # 4. 定位电话按钮
            if not info_data['phone_button_pos']:
                if '电话' in clean_text or '补充电话' in clean_text:
                    info_data['phone_button_pos'] = {
                        'x': (bounds['x1'] + bounds['x2']) // 2,
                        'y': (bounds['y1'] + bounds['y2']) // 2
                    }
                    if debug_mode:
                        print(f"    ✓ 电话按钮: ({info_data['phone_button_pos']['x']}, {info_data['phone_button_pos']['y']}) (Y={bounds['y1']})")

        return info_data

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

    def _is_excluded_name(self, text: str) -> bool:
        """
        判断是否是需要排除的商家名

        Args:
            text: 文本内容

        Returns:
            是否需要排除
        """
        # 排除照片标签
        if re.match(r'^照片\(\d+\)$', text):
            return True
        if text.startswith('照片') or '相册' in text:
            return True

        # 排除评分
        if re.match(r'^\d+\.\d+$', text):
            return True
        if re.match(r'^\d+\.\d+\s*分', text):
            return True

        # 排除时间
        if re.match(r'^\d{2}:\d{2}', text):
            return True

        # 排除营业状态
        if text in ['营业中', '休息中', '即将营业', '已打烊', '暂停营业']:
            return True

        # 排除页面标签
        if text in ['入驻商家', '刚刚浏览', '达人笔记', '附近推荐', '查看全部']:
            return True

        # 排除商品名标识
        if '【' in text or '】' in text:
            return True

        return False
