# 智能商家信息采集器 - 使用说明

## 🎯 核心理念

**先验证，再定位，实时确认，精准提取**

传统方法的问题：
- ❌ 直接定位点击，不验证页面状态
- ❌ 点击后不确认是否进入正确页面
- ❌ 盲目提取信息，容易出错

新的智能流程：
- ✅ 第1步：页面状态识别 - 确认是搜索结果页
- ✅ 第2步：商家卡片定位 - 精确定位每个卡片
- ✅ 第3步：安全点击执行 - 点击商家卡片
- ✅ 第4步：结果验证确认 - 验证是否进入正确详情页
- ✅ 第5步：信息提取保存 - 提取并保存商家信息

---

## 📁 文件结构

```
D:\info\
├── page_state_analyzer.py      # 页面状态分析器（新）
├── merchant_card_locator.py    # 商家卡片定位器（已优化）
├── smart_collector.py          # 智能采集器（新）
├── test_smart_collector.py     # 测试脚本（新）
├── adb_manager.py              # ADB设备管理器
├── config.yaml                 # 配置文件
└── SMART_COLLECTOR_README.md   # 本文档
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install lxml pyyaml
```

### 2. 连接设备

```bash
adb devices
```

### 3. 打开高德地图

1. 在手机上打开高德地图
2. 搜索目标类别（如"鲜花"）
3. 确保显示商家列表页面

### 4. 运行测试脚本

```bash
python test_smart_collector.py
```

---

## 🔍 详细流程说明

### 步骤1：页面状态识别

**目的**：确认当前页面是否为搜索结果页，是否包含商家列表

**实现**：`PageStateAnalyzer.analyze_page()`

**验证内容**：
- ✅ 是否有RecyclerView（列表容器）
- ✅ 是否有多个可点击的ViewGroup（至少3个）
- ✅ 识别布局类型（全屏宽度 vs 窄版布局）
- ✅ 估算商家卡片数量
- ✅ 提取页面特征（评分、距离、营业状态等）

**输出示例**：
```python
{
    'page_type': 'search_result',
    'has_merchant_list': True,
    'merchant_count': 5,
    'layout_type': 'narrow',  # 或 'full_width'
    'confidence': 0.85,
    'features': ['has_recyclerview', 'has_rating', 'has_distance']
}
```

---

### 步骤2：商家卡片定位

**目的**：精确定位每个商家卡片的位置和安全点击区域

**实现**：`MerchantCardLocator.find_merchant_cards()`

**定位策略**：
- 🔍 策略1：从RecyclerView中查找（主要）
- 🔍 策略2：从content-desc属性查找（备用）

**多层过滤**：
1. Y轴过滤：500 < Y < 1800（过滤顶部广告和底部元素）
2. 宽度过滤：60%-98%（支持多种布局）
3. 高度过滤：100-450像素（支持纯文本和带图片）
4. 关键词过滤：排除广告、标签、距离等

**安全点击计算**：
```
商家卡片结构：
┌────────────────────────────────────────┐
│ [商家名称]        [收藏][电话][导航]  │
│ 地址: xxx              距离: 5km      │
└────────────────────────────────────────┘
  ↑ 安全区域(10%-60%)   ↑ 按钮区(60%-100%)
```

点击位置：卡片左侧10%-60%区域的中心点

**输出示例**：
```python
[
    {
        'name': '成都郊然光域鲜花店',
        'bounds': {'x1': 33, 'y1': 533, 'x2': 1047, 'y2': 731, 'width': 1014, 'height': 198},
        'click_point': {'x': 387, 'y': 632},
        'confidence': 0.90,
        'index': 0
    },
    # ...更多卡片
]
```

---

### 步骤3：安全点击执行

**目的**：点击商家卡片，尝试进入详情页

**实现**：
```python
adb.tap(click_point['x'], click_point['y'])
time.sleep(2.0)  # 等待页面加载
```

**点击策略**：
- 点击卡片左侧区域（避开右侧按钮）
- 点击垂直中部（避开顶部和底部）
- 等待2秒确保页面完全加载

---

### 步骤4：结果验证确认

**目的**：验证是否成功进入了正确的商家详情页

**实现**：`PageStateAnalyzer.verify_merchant_detail_page()`

**验证内容**：
- ✅ 是否是详情页（检查特征关键词）
- ✅ 是否有电话号码
- ✅ 是否有地址信息
- ✅ 商家名是否匹配期望值

**输出示例**：
```python
{
    'is_detail_page': True,
    'merchant_name': '成都郊然光域鲜花店',
    'has_phone': True,
    'has_address': True,
    'match_expected': True,
    'confidence': 0.80
}
```

**失败处理**：
- 如果未进入详情页 → 返回搜索结果页，跳过当前商家
- 如果商家名不匹配 → 记录警告，但仍提取信息
- 如果置信度过低 → 标记为低质量数据

---

### 步骤5：信息提取保存

**目的**：从详情页提取商家完整信息

**实现**：`SmartCollector._extract_merchant_info()`

**提取内容**：
- 📱 **电话号码**：正则提取1[3-9]\d{9}
- 📍 **地址**：提取四川省/云南省/成都市/昆明市开头的地址
- ⏰ **营业时间**：提取时间格式（08:00-22:00）
- ⭐ **评分**：提取X.X分格式
- 📄 **原始文本**：保存前500字符供后续分析

**输出示例**：
```python
{
    'name': '成都郊然光域鲜花店',
    'phones': ['13812345678', '18987654321'],
    'address': '四川省成都市温江区欧部1栋一单元4楼18号',
    'business_hours': '08:00-22:00',
    'rating': '4.4',
    'raw_text': '成都郊然光域鲜花店...'
}
```

**数据验证**：
- 至少有1个电话号码
- 地址长度 >= 10个字符
- 商家名不为空

---

## 🎨 适配多种布局

### 昆明布局（全屏宽度）
```
屏幕宽度: 1080px
卡片宽度: 1014px (94%)
Y轴起始: 612px
```

### 成都布局（窄版布局）
```
屏幕宽度: 1080px
卡片宽度: 717px (66%)
Y轴起始: 533px
```

**置信度评分**：
- 全屏宽度（90%-95%）：置信度 1.0
- 窄版布局（64%-70%）：置信度 0.9
- 其他宽度：置信度 0.7-0.85

---

## 📊 统计信息

采集器会实时统计：
- ✅ 尝试采集数
- ✅ 成功采集数
- ✅ 失败采集数
- ✅ 错误页面数（点击后未进入详情页）
- ✅ 提取错误数
- ✅ 成功率

**示例输出**：
```
================================================================================
📊 采集统计
================================================================================
尝试采集: 5
成功采集: 4 ✓
失败采集: 1 ✗
错误页面: 0
提取错误: 1
成功率: 80.0%
================================================================================
```

---

## 🛠️ 高级配置

### config.yaml 参数说明

```yaml
locator_params:
  safe_y_min: 500              # Y轴最小值（过滤顶部广告）
  safe_y_max: 1800             # Y轴最大值（过滤底部元素）
  min_width_ratio: 0.60        # 最小宽度比例（支持66%和94%）
  max_width_ratio: 0.98        # 最大宽度比例
  min_height: 100              # 最小高度（像素）
  max_height: 450              # 最大高度（支持带图片卡片）
  click_zone_left_ratio: 0.1   # 安全点击区左边界
  click_zone_right_ratio: 0.6  # 安全点击区右边界
  click_zone_top_ratio: 0.3    # 安全点击区顶部
  click_zone_bottom_ratio: 0.7 # 安全点击区底部
```

### 调整建议

**如果遗漏商家**：
- 降低 `safe_y_min`（如500→450）
- 降低 `min_width_ratio`（如0.60→0.55）

**如果识别到广告**：
- 提高 `safe_y_min`（如500→550）
- 增加广告关键词到 `ad_keywords`

**如果点击错误位置**：
- 调整 `click_zone_right_ratio`（如0.6→0.5）
- 调整 `click_zone_top_ratio` 和 `bottom_ratio`

---

## 🔧 调试技巧

### 1. 启用调试模式

```python
result = collector.collect_from_search_page(debug=True)
```

**输出详细信息**：
- 页面分析结果
- 每个节点的验证过程
- 点击位置和置信度
- 详情页验证结果

### 2. 查看XML层级

```python
xml = adb.get_ui_hierarchy()
with open('debug_hierarchy.xml', 'w', encoding='utf-8') as f:
    f.write(xml)
```

### 3. 单步测试

```python
# 只测试页面识别
page_info = collector.page_analyzer.analyze_page(xml_content, debug=True)

# 只测试卡片定位
cards = collector.card_locator.find_merchant_cards(xml_content, debug_mode=True)

# 只测试详情页验证
verify_result = collector.page_analyzer.verify_merchant_detail_page(xml_content)
```

---

## ⚠️ 常见问题

### Q1: 识别不到商家卡片？

**原因**：
- Y轴过滤过严（safe_y_min太高）
- 宽度过滤过严（min_width_ratio太高）

**解决**：
- 查看日志中被过滤的节点
- 适当降低过滤参数

### Q2: 点击后进入错误页面？

**原因**：
- 点击位置不准确
- 卡片右侧按钮被误点

**解决**：
- 减小 `click_zone_right_ratio`
- 检查 `click_point` 坐标是否在安全区域

### Q3: 信息提取不完整？

**原因**：
- 正则表达式匹配失败
- 详情页加载不完全

**解决**：
- 增加等待时间（`time.sleep(2.0)` → `3.0`）
- 检查 `raw_text` 中是否包含目标信息
- 优化正则表达式

---

## 🎯 最佳实践

1. **采集前准备**
   - 确保网络稳定
   - 关闭其他应用通知
   - 保持手机屏幕常亮

2. **采集中监控**
   - 观察调试输出
   - 检查采集成功率
   - 及时调整参数

3. **采集后处理**
   - 验证数据完整性
   - 去重处理
   - 保存到数据库

4. **错误处理**
   - 记录失败的商家名
   - 手动复查低置信度数据
   - 定期更新过滤规则

---

## 📚 API参考

### PageStateAnalyzer

```python
analyzer = PageStateAnalyzer()

# 分析页面状态
page_info = analyzer.analyze_page(xml_content, debug=True)

# 验证详情页
verify_result = analyzer.verify_merchant_detail_page(
    xml_content,
    expected_name="商家名"
)
```

### MerchantCardLocator

```python
locator = MerchantCardLocator(screen_width=1080, screen_height=2340)

# 查找商家卡片
cards = locator.find_merchant_cards(xml_content, debug_mode=True)
```

### SmartCollector

```python
collector = SmartCollector(adb_manager, screen_width, screen_height)

# 执行采集
result = collector.collect_from_search_page(debug=True)
```

---

## 🎓 设计原则

1. **先验证后操作**：每步都验证状态，避免盲目操作
2. **实时反馈**：每步都输出结果，方便调试
3. **容错处理**：失败不中断，记录统计信息
4. **模块化设计**：每个模块职责单一，易于测试
5. **可配置性**：参数外部化，适应不同场景

---

**版本**: 1.0
**作者**: Claude Code
**日期**: 2025-01-16
**更新**: 首次发布智能采集流程
