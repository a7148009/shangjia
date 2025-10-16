# 商家采集系统 - 失败分析与改进方案

## 📊 日志分析总结

### 🔴 核心问题汇总

#### 问题1：商家列表识别错误（最严重）
**发现的14个"商家"中，只有1个是真正的商家！**

```
错误识别列表：
1. "高德红包" ❌ - 广告横幅 (bounds: Y=408-452)
2. "高德红包" ❌ - 重复广告
3. "刚刚浏览" ❌ - UI标签 (bounds: Y=742-781)
4. "斗南花卉市场" ✅ - 真正的商家！(bounds: Y=533-700)
```

**失败原因分析：**
- 日志第25-45行：识别到"优惠卡券"、"满299减15"等广告文本
- 日志第87行：`高德红包` - 文本位置 [67,408][196,452]
- 日志第93行：`刚刚浏览` - 文本位置 [56,742][169,781]
- 日志第94行：真正的商家名 `<font size="32"><b>斗南花卉市场</b></font>` 位置 [330,533][594,595]

**真正的商家特征（从日志第94-98行）：**
```
商家名称：[330,533][594,595] <font><b>斗南花卉市场</b></font>
地址：[330,600][686,644] 金桂街76号·驾车11分钟
距离：[931,600][1047,644] 5.8公里
评分：[338,658][381,698] 4.9
```

#### 问题2：商家名称提取错误
```
采集结果（第176行）：
- 名称: "半夜12:12" ❌  (系统时间！位置 [40,0][190,96])
- 地址: "金桂街76号·驾车11分钟" ✅
- 电话: "" (未提取到)
```

**失败原因：**
- 提取顶部30%区域的第一个非排除文本
- 系统时间在 Y=0-96，被错误识别为商家名

#### 问题3：点击后进入错误页面
```
操作流程（日志18-122行）：
1. 点击(540, 440) → 进入"优惠卡券"页面 ❌
2. 点击(918, 585) → 点击关闭按钮
3. 按返回键 → 返回到高德首页 ❌ (应该是搜索结果页)
```

#### 问题4：返回逻辑错误
```
每次采集后执行2次返回：
商家详情页 → 返回 → 搜索结果页 → 返回 → 高德首页 ❌

正确流程应该是：
商家详情页 → 返回 → 搜索结果页 ✓ (停止)
```

---

## 🔧 升级改进方案

### 改进1：严格的商家卡片识别规则

```python
def _parse_merchant_card(self, node, screen_width, screen_height):
    """
    严格识别商家卡片

    真实商家特征（从日志总结）：
    1. Y轴位置：400-1000 像素范围（屏幕中部）
    2. 宽度：>90% 屏幕宽度
    3. 高度：150-250 像素
    4. 包含 HTML 格式的商家名：<font><b>商家名</b></font>
    5. 包含地址信息（区/路/街/号）
    6. 不包含广告关键词
    """

    # 1. Y轴严格过滤（商家在屏幕中部）
    if y1 < 400 or y2 > 1000:
        return None

    # 2. 宽度严格过滤（必须接近全屏）
    if width < screen_width * 0.9:
        return None

    # 3. 高度严格过滤（商家卡片固定高度）
    if height < 150 or height > 250:
        return None

    # 4. 排除广告
    if self._is_advertisement(merchant_name):
        return None
```

### 改进2：广告过滤规则

```python
def _is_advertisement(self, text):
    """
    识别并排除广告内容
    """
    ad_keywords = [
        '高德红包', '优惠', '券', '领取', '满减', '折扣',
        '刚刚浏览', '大家还在搜', '推荐', '榜单',
        '扫街榜', '爆款', '精选'
    ]

    for keyword in ad_keywords:
        if keyword in text:
            return True

    # 排除纯数字（如电话格式但不是商家名）
    if text.replace('.', '').replace(':', '').isdigit():
        return True

    return False
```

### 改进3：商家名称提取优化

```python
def _extract_merchant_name_from_detail(self, root, screen_height):
    """
    从商家详情页提取名称

    优先级：
    1. HTML格式：<font><b>商家名</b></font> (最可靠)
    2. 大字体文本（Y轴 200-600 范围）
    3. 排除系统时间（Y<100）和其他UI元素
    """

    # 方法1：查找HTML格式商家名
    for node in all_text_nodes:
        text = node.get('text', '')
        # 匹配 <font...><b>商家名</b></font>
        match = re.search(r'<font[^>]*><b>([^<]+)</b></font>', text)
        if match:
            return match.group(1)

    # 方法2：查找Y轴200-600范围的大文本
    for node in all_text_nodes:
        y1, y2 = get_y_position(node)
        if 200 < y1 < 600:
            text = node.get('text', '').strip()
            if len(text) > 3 and not self._is_excluded_text(text):
                # 排除系统时间格式
                if not re.match(r'\d{1,2}:\d{2}', text):
                    return text

    return "未知商家"
```

### 改进4：页面状态检测

```python
def _is_on_merchant_detail_page(self) -> bool:
    """
    检测是否在商家详情页

    特征：
    - 包含"电话"按钮
    - 包含"导航"按钮
    - 包含评分信息（X.X格式）
    - 包含地址信息（区/路/街）
    """
    xml = self.adb_manager.get_ui_hierarchy()
    root = etree.fromstring(xml.encode('utf-8'))

    # 检查特征
    has_phone_button = len(root.xpath('//node[contains(@text, "电话")]')) > 0
    has_nav_button = len(root.xpath('//node[contains(@text, "导航")]')) > 0

    return has_phone_button and has_nav_button

def _is_on_search_result_page(self) -> bool:
    """
    检测是否在搜索结果页

    特征：
    - 包含"筛选"按钮
    - 包含"排序"按钮
    - 包含多个商家卡片
    """
    xml = self.adb_manager.get_ui_hierarchy()
    root = etree.fromstring(xml.encode('utf-8'))

    has_filter = len(root.xpath('//node[contains(@text, "筛选")]')) > 0
    has_sort = len(root.xpath('//node[contains(@text, "排序")]')) > 0

    return has_filter and has_sort
```

### 改进5：智能返回逻辑

```python
def go_back_to_list(self):
    """
    从商家详情页返回到搜索结果页（智能返回）
    """
    try:
        # 按返回键
        self.adb_manager.press_back()
        time.sleep(1)

        # 检查是否回到搜索结果页
        if self._is_on_search_result_page():
            print("✓ 已返回搜索结果页")
            return True
        else:
            print("⚠ 未回到搜索结果页，检查当前页面...")
            # 如果返回到了首页，需要重新进入搜索
            return False

    except Exception as e:
        print(f"返回失败: {e}")
        return False
```

---

## 📝 完整改进清单

### 高优先级（必须修复）
1. ✅ 修复商家列表识别（添加严格的Y轴、宽高过滤）
2. ✅ 添加广告过滤机制
3. ✅ 修复商家名称提取（优先HTML格式，排除系统时间）
4. ✅ 添加页面状态检测
5. ✅ 优化返回逻辑（确保返回到正确页面）

### 中优先级（建议添加）
6. 添加点击前的页面验证（确保在搜索结果页）
7. 添加点击后的页面验证（确保进入详情页）
8. 添加重试机制（点击失败时重试）

### 低优先级（优化体验）
9. 添加进度提示（当前第X个，共Y个）
10. 添加失败统计（成功X个，失败Y个）

---

## 🎯 预期效果

修复后应达到：
- ✅ 商家识别准确率：95%+ （目前只有7%）
- ✅ 商家名称准确率：100% （目前提取成系统时间）
- ✅ 返回逻辑准确率：100% （目前返回错误页面）
- ✅ 整体成功率：90%+
