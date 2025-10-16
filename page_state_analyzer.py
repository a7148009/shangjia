"""
页面状态分析器
用于识别当前高德地图页面的状态类型，判断是否包含商家卡片列表

核心功能：
1. 识别页面类型（搜索结果页、商家详情页、地图页等）
2. 验证是否有商家卡片列表
3. 提取页面关键元素信息
4. 支持多城市布局差异
"""
import re
from typing import Dict, List, Optional
from lxml import etree


class PageStateAnalyzer:
    """页面状态分析器"""

    # 页面类型常量
    PAGE_TYPE_SEARCH_RESULT = "search_result"      # 搜索结果页
    PAGE_TYPE_MERCHANT_DETAIL = "merchant_detail"  # 商家详情页
    PAGE_TYPE_MAP_VIEW = "map_view"                # 地图视图
    PAGE_TYPE_UNKNOWN = "unknown"                  # 未知页面

    def __init__(self):
        """初始化分析器"""
        # 搜索结果页特征关键词
        self.search_result_keywords = [
            'RecyclerView',  # 列表容器
            '搜索', '附近', '筛选',
            '高德甄选', '高德推荐'
        ]

        # 商家详情页特征关键词
        self.detail_page_keywords = [
            '拨打电话', '到这去', '收藏', '分享',
            '地址', '营业时间', '简介'
        ]

        # 商家卡片特征
        self.merchant_card_patterns = [
            r'花店|花卉|鲜花|花艺',  # 商家名称模式
            r'四川省|成都|昆明',      # 地址模式
            r'\d+人去过|\d+人咨询',   # 统计信息
            r'营业中|已打烊',         # 营业状态
        ]

    def analyze_page(self, xml_content: str, debug: bool = False) -> Dict:
        """
        分析页面状态

        Args:
            xml_content: UI层级XML内容
            debug: 是否启用调试输出

        Returns:
            分析结果字典：
            {
                'page_type': str,           # 页面类型
                'has_merchant_list': bool,  # 是否包含商家列表
                'merchant_count': int,      # 商家卡片数量（估算）
                'layout_type': str,         # 布局类型（full_width/narrow）
                'confidence': float,        # 置信度
                'features': List[str]       # 识别到的特征
            }
        """
        if not xml_content:
            return self._empty_result("XML内容为空")

        try:
            root = etree.fromstring(xml_content.encode('utf-8'))

            # 第1步：识别页面类型
            page_type = self._identify_page_type(root)

            # 第2步：检查是否有商家列表
            has_merchant_list = self._has_merchant_list(root)

            # 第3步：估算商家卡片数量
            merchant_count = self._estimate_merchant_count(root)

            # 第4步：识别布局类型
            layout_type = self._identify_layout_type(root)

            # 第5步：提取页面特征
            features = self._extract_features(root)

            # 第6步：计算置信度
            confidence = self._calculate_confidence(
                page_type, has_merchant_list, merchant_count, features
            )

            result = {
                'page_type': page_type,
                'has_merchant_list': has_merchant_list,
                'merchant_count': merchant_count,
                'layout_type': layout_type,
                'confidence': confidence,
                'features': features
            }

            if debug:
                self._print_analysis_result(result)

            return result

        except Exception as e:
            if debug:
                print(f"✗ 页面分析失败: {e}")
                import traceback
                traceback.print_exc()
            return self._empty_result(f"分析异常: {e}")

    def _identify_page_type(self, root) -> str:
        """识别页面类型"""
        # 查找RecyclerView（搜索结果页的列表容器）
        recyclerviews = root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')
        if recyclerviews:
            return self.PAGE_TYPE_SEARCH_RESULT

        # 查找商家详情页特征
        all_text = self._get_all_text(root)
        detail_keywords_found = sum(1 for kw in self.detail_page_keywords if kw in all_text)
        if detail_keywords_found >= 3:
            return self.PAGE_TYPE_MERCHANT_DETAIL

        # 其他情况
        return self.PAGE_TYPE_UNKNOWN

    def _has_merchant_list(self, root) -> bool:
        """检查是否有商家列表"""
        # 策略1：查找RecyclerView
        recyclerviews = root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')
        if not recyclerviews:
            return False

        # 策略2：查找ViewGroup列表项（至少3个才算列表）
        for recyclerview in recyclerviews:
            viewgroups = recyclerview.xpath(
                './/node[@class="android.view.ViewGroup" and @clickable="true"]'
            )
            if len(viewgroups) >= 3:
                return True

        return False

    def _estimate_merchant_count(self, root) -> int:
        """估算商家卡片数量"""
        recyclerviews = root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')
        if not recyclerviews:
            return 0

        max_count = 0
        for recyclerview in recyclerviews:
            # 查找可点击的ViewGroup
            viewgroups = recyclerview.xpath(
                './/node[@class="android.view.ViewGroup" and @clickable="true" and @bounds]'
            )

            # 过滤：只统计高度在100-500范围内的节点
            valid_cards = []
            for vg in viewgroups:
                bounds_str = vg.get('bounds', '')
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    height = y2 - y1
                    if 100 <= height <= 500:
                        valid_cards.append(vg)

            max_count = max(max_count, len(valid_cards))

        return max_count

    def _identify_layout_type(self, root) -> str:
        """
        识别布局类型

        Returns:
            'full_width': 全屏宽度布局（昆明等）
            'narrow': 窄版布局（成都等）
            'unknown': 未知布局
        """
        recyclerviews = root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]')
        if not recyclerviews:
            return 'unknown'

        # 采样检查前3个ViewGroup的宽度
        for recyclerview in recyclerviews:
            viewgroups = recyclerview.xpath(
                './/node[@class="android.view.ViewGroup" and @clickable="true" and @bounds]'
            )[:3]

            for vg in viewgroups:
                bounds_str = vg.get('bounds', '')
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    width = x2 - x1

                    # 假设屏幕宽度1080
                    width_ratio = width / 1080
                    if width_ratio >= 0.85:
                        return 'full_width'
                    elif 0.60 <= width_ratio < 0.75:
                        return 'narrow'

        return 'unknown'

    def _extract_features(self, root) -> List[str]:
        """提取页面特征"""
        features = []
        all_text = self._get_all_text(root)

        # 检查RecyclerView
        if root.xpath('//node[@class="androidx.recyclerview.widget.RecyclerView"]'):
            features.append('has_recyclerview')

        # 检查商家名称模式
        for pattern in self.merchant_card_patterns:
            if re.search(pattern, all_text):
                features.append(f'pattern:{pattern[:10]}')

        # 检查是否有评分信息
        if re.search(r'\d\.\d\s*分|很好|超棒', all_text):
            features.append('has_rating')

        # 检查是否有距离信息
        if re.search(r'\d+\.?\d*\s?(公里|km|米|m)', all_text):
            features.append('has_distance')

        # 检查是否有营业状态
        if re.search(r'营业中|已打烊|暂停营业', all_text):
            features.append('has_business_status')

        return features

    def _calculate_confidence(
        self, page_type: str, has_merchant_list: bool,
        merchant_count: int, features: List[str]
    ) -> float:
        """计算页面识别置信度"""
        confidence = 0.0

        # 因素1：页面类型（40分）
        if page_type == self.PAGE_TYPE_SEARCH_RESULT:
            confidence += 0.4
        elif page_type == self.PAGE_TYPE_MERCHANT_DETAIL:
            confidence += 0.2
        else:
            confidence += 0.1

        # 因素2：商家列表存在性（30分）
        if has_merchant_list:
            confidence += 0.3

        # 因素3：商家数量（20分）
        if merchant_count >= 3:
            confidence += 0.2
        elif merchant_count >= 1:
            confidence += 0.1

        # 因素4：特征数量（10分）
        feature_score = min(len(features) * 0.02, 0.1)
        confidence += feature_score

        return min(confidence, 1.0)

    def _get_all_text(self, root) -> str:
        """获取页面所有文本内容"""
        texts = []

        # 从content-desc获取
        for node in root.xpath('//node[@content-desc]'):
            desc = node.get('content-desc', '').strip()
            if desc:
                texts.append(desc)

        # 从text属性获取
        for node in root.xpath('//node[@text]'):
            text = node.get('text', '').strip()
            if text:
                texts.append(text)

        return ' '.join(texts)

    def _empty_result(self, reason: str) -> Dict:
        """返回空结果"""
        return {
            'page_type': self.PAGE_TYPE_UNKNOWN,
            'has_merchant_list': False,
            'merchant_count': 0,
            'layout_type': 'unknown',
            'confidence': 0.0,
            'features': [],
            'error': reason
        }

    def _print_analysis_result(self, result: Dict):
        """打印分析结果"""
        print("\n" + "="*80)
        print("📊 页面状态分析结果")
        print("="*80)
        print(f"页面类型: {result['page_type']}")
        print(f"包含商家列表: {'✓ 是' if result['has_merchant_list'] else '✗ 否'}")
        print(f"商家卡片数量: {result['merchant_count']}")
        print(f"布局类型: {result['layout_type']}")
        print(f"置信度: {result['confidence']:.2%}")
        print(f"识别特征: {', '.join(result['features']) if result['features'] else '无'}")
        if 'error' in result:
            print(f"⚠ 错误: {result['error']}")
        print("="*80 + "\n")

    def verify_merchant_detail_page(self, xml_content: str, expected_name: str = None) -> Dict:
        """
        验证是否进入了正确的商家详情页

        Args:
            xml_content: UI层级XML内容
            expected_name: 期望的商家名称（可选）

        Returns:
            验证结果字典：
            {
                'is_detail_page': bool,      # 是否是详情页
                'merchant_name': str,        # 提取到的商家名
                'has_phone': bool,           # 是否有电话号码
                'has_address': bool,         # 是否有地址
                'match_expected': bool,      # 是否匹配期望的商家名
                'confidence': float          # 验证置信度
            }
        """
        if not xml_content:
            return {
                'is_detail_page': False,
                'merchant_name': '',
                'has_phone': False,
                'has_address': False,
                'match_expected': False,
                'confidence': 0.0
            }

        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            all_text = self._get_all_text(root)

            # 检查详情页特征
            is_detail_page = self._identify_page_type(root) == self.PAGE_TYPE_MERCHANT_DETAIL

            # 提取商家名（通常在页面顶部）
            merchant_name = self._extract_merchant_name_from_detail(root)

            # 检查是否有电话号码
            has_phone = bool(re.search(r'1[3-9]\d{9}|拨打电话|电话', all_text))

            # 检查是否有地址
            has_address = bool(re.search(r'地址|四川省|成都|昆明|区.*路|街道', all_text))

            # 检查是否匹配期望的商家名
            match_expected = False
            if expected_name and merchant_name:
                # 模糊匹配：提取关键词
                expected_keywords = set(expected_name.replace(' ', ''))
                merchant_keywords = set(merchant_name.replace(' ', ''))
                common = expected_keywords & merchant_keywords
                match_expected = len(common) >= min(4, len(expected_keywords) * 0.5)

            # 计算置信度
            confidence = 0.0
            if is_detail_page:
                confidence += 0.4
            if has_phone:
                confidence += 0.2
            if has_address:
                confidence += 0.2
            if match_expected:
                confidence += 0.2

            return {
                'is_detail_page': is_detail_page,
                'merchant_name': merchant_name,
                'has_phone': has_phone,
                'has_address': has_address,
                'match_expected': match_expected,
                'confidence': confidence
            }

        except Exception as e:
            print(f"✗ 详情页验证失败: {e}")
            return {
                'is_detail_page': False,
                'merchant_name': '',
                'has_phone': False,
                'has_address': False,
                'match_expected': False,
                'confidence': 0.0
            }

    def _extract_merchant_name_from_detail(self, root) -> str:
        """从详情页提取商家名称"""
        # 策略1：查找页面顶部的大标题（通常Y坐标 < 500）
        nodes = root.xpath('//node[@text and @bounds]')
        candidates = []

        for node in nodes:
            text = node.get('text', '').strip()
            bounds_str = node.get('bounds', '')

            if not text or len(text) < 3:
                continue

            # 解析坐标
            match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())

                # 顶部区域，较大字号（推断）
                if y1 < 500 and len(text) >= 4:
                    candidates.append((y1, text))

        # 选择Y坐标最小的（最靠近顶部）
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        return ""
