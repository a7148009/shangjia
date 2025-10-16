# 智能商家采集系统 - 架构设计

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        智能采集系统                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────┐
        │      SmartCollector (智能采集器)      │
        │   - 流程控制                          │
        │   - 统计管理                          │
        │   - 错误处理                          │
        └───────────────────────────────────────┘
                │               │              │
        ┌───────┴───────┐   ┌──┴──────┐   ┌──┴──────────┐
        ▼               ▼   ▼         ▼   ▼             ▼
┌──────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐
│PageState     │  │MerchantCard │  │ADBDevice    │  │Database  │
│Analyzer      │  │Locator      │  │Manager      │  │Manager   │
│              │  │             │  │             │  │          │
│页面状态识别  │  │卡片精确定位 │  │设备控制     │  │数据存储  │
└──────────────┘  └─────────────┘  └─────────────┘  └──────────┘
```

---

## 核心模块职责

### 1. SmartCollector（智能采集器）

**职责**：流程编排和控制

**核心方法**：
```python
collect_from_search_page()  # 主流程入口
  ├─ _collect_single_merchant()  # 单个商家采集
  ├─ _extract_merchant_info()    # 信息提取
  ├─ _click_point()               # 点击操作
  ├─ _go_back()                   # 返回操作
  └─ _print_statistics()          # 统计输出
```

**依赖**：
- PageStateAnalyzer（页面分析）
- MerchantCardLocator（卡片定位）
- ADBDeviceManager（设备控制）

---

### 2. PageStateAnalyzer（页面状态分析器）

**职责**：识别页面类型和状态

**核心方法**：
```python
analyze_page()                    # 分析页面状态
  ├─ _identify_page_type()        # 识别页面类型
  ├─ _has_merchant_list()         # 检查商家列表
  ├─ _estimate_merchant_count()   # 估算商家数量
  ├─ _identify_layout_type()      # 识别布局类型
  ├─ _extract_features()          # 提取页面特征
  └─ _calculate_confidence()      # 计算置信度

verify_merchant_detail_page()     # 验证详情页
  └─ _extract_merchant_name_from_detail()
```

**页面类型**：
- `search_result` - 搜索结果页
- `merchant_detail` - 商家详情页
- `map_view` - 地图视图
- `unknown` - 未知页面

**布局类型**：
- `full_width` - 全屏宽度（94%，昆明等）
- `narrow` - 窄版布局（66%，成都等）
- `unknown` - 未知布局

---

### 3. MerchantCardLocator（商家卡片定位器）

**职责**：精确定位商家卡片位置

**核心方法**：
```python
find_merchant_cards()              # 查找商家卡片
  ├─ _extract_from_recyclerview()  # 策略1：从RecyclerView
  ├─ _extract_from_contentdesc()   # 策略2：从content-desc
  └─ _merge_cards()                # 合并去重

_parse_single_card()               # 解析单个卡片
  ├─ _parse_bounds()               # 解析坐标
  ├─ _validate_bounds()            # 验证有效性
  ├─ _extract_merchant_name()      # 提取商家名
  ├─ _is_advertisement()           # 广告过滤
  ├─ _calculate_safe_click_point() # 计算点击位置
  └─ _calculate_confidence()       # 计算置信度
```

**多层过滤机制**：
```
XML节点
   │
   ├─ 过滤1: Y轴范围 (500 < Y < 1800)
   │         ↓
   ├─ 过滤2: 宽度比例 (60%-98%)
   │         ↓
   ├─ 过滤3: 高度范围 (100-450px)
   │         ↓
   ├─ 过滤4: 提取商家名
   │         ↓
   ├─ 过滤5: 广告关键词过滤
   │         ↓
   └─ 合格商家卡片 ✓
```

---

### 4. ADBDeviceManager（ADB设备管理器）

**职责**：Android设备交互

**核心方法**：
```python
connect()              # 连接设备
get_ui_hierarchy()     # 获取UI层级XML
tap(x, y)              # 点击屏幕
press_key(keycode)     # 按键操作
get_screen_size()      # 获取屏幕尺寸
capture_screenshot()   # 截图
```

**依赖**：
- adb命令行工具
- USB调试开启

---

## 数据流转图

```
┌──────────┐
│ 启动采集 │
└────┬─────┘
     │
     ▼
┌─────────────────┐
│ 1. 获取UI层级   │ ← adb shell uiautomator dump
└────┬────────────┘
     │
     ▼
┌──────────────────┐
│ 2. 页面状态分析  │
│  - 识别页面类型  │ → 是搜索结果页？
│  - 检查商家列表  │ → 有商家列表？
│  - 识别布局类型  │ → 全屏 or 窄版？
└────┬─────────────┘
     │ YES
     ▼
┌──────────────────┐
│ 3. 商家卡片定位  │
│  - 查找RecyclerView
│  - 多层过滤验证  │
│  - 提取商家名称  │
│  - 计算点击位置  │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────┐
│ 4. 逐个点击卡片  │ ──→ │点击商家1 │
└────┬─────────────┘     └────┬─────┘
     │                        │
     │                        ▼
     │              ┌──────────────────┐
     │              │ 5. 验证详情页    │
     │              │  - 是详情页？    │ → NO → 返回继续
     │              │  - 商家名匹配？  │
     │              │  - 有电话地址？  │
     │              └────┬─────────────┘
     │                   │ YES
     │                   ▼
     │              ┌──────────────────┐
     │              │ 6. 提取信息      │
     │              │  - 商家名        │
     │              │  - 电话号码      │
     │              │  - 地址          │
     │              │  - 营业时间      │
     │              │  - 评分          │
     │              └────┬─────────────┘
     │                   │
     │                   ▼
     │              ┌──────────────────┐
     │              │ 7. 保存数据      │
     │              └────┬─────────────┘
     │                   │
     │                   ▼
     │              ┌──────────────────┐
     │              │ 8. 返回搜索页    │
     │              └────┬─────────────┘
     │                   │
     └───────────────────┘
     │
     ▼
┌──────────────────┐
│ 9. 输出统计结果  │
│  - 成功数        │
│  - 失败数        │
│  - 成功率        │
└──────────────────┘
```

---

## 配置参数层次

```yaml
# config.yaml

locator_params:               # 卡片定位参数
  safe_y_min: 500            # Y轴过滤
  safe_y_max: 1800
  min_width_ratio: 0.60      # 宽度过滤
  max_width_ratio: 0.98
  min_height: 100            # 高度过滤
  max_height: 450
  click_zone_left_ratio: 0.1  # 点击区域
  click_zone_right_ratio: 0.6
  click_zone_top_ratio: 0.3
  click_zone_bottom_ratio: 0.7

collection:                   # 采集行为参数
  wait_after_click: 2.0      # 点击后等待
  wait_after_back: 1.5       # 返回后等待
  max_retry_attempts: 3      # 最大重试次数

ad_keywords:                  # 广告过滤关键词
  - "高德红包"
  - "优惠券"
  - "鲜花配送"
  # ... 更多

excluded_keywords:            # 排除关键词
  - "搜索"
  - "导航"
  - "附近"
  # ... 更多
```

---

## 置信度评分体系

### 页面识别置信度

```python
confidence = 0.0

# 因素1: 页面类型（40%权重）
if page_type == 'search_result':
    confidence += 0.4

# 因素2: 商家列表（30%权重）
if has_merchant_list:
    confidence += 0.3

# 因素3: 商家数量（20%权重）
if merchant_count >= 3:
    confidence += 0.2

# 因素4: 页面特征（10%权重）
confidence += min(len(features) * 0.02, 0.1)

总置信度 = min(confidence, 1.0)
```

### 卡片定位置信度

```python
confidence = 1.0

# 因素1: Y轴位置
if 600 <= y <= 1500:
    confidence *= 1.0  # 核心区域

# 因素2: 宽度比例
if 0.90 <= width_ratio <= 0.95:
    confidence *= 1.0  # 全屏布局
elif 0.64 <= width_ratio <= 0.70:
    confidence *= 0.90  # 窄版布局

# 因素3: 高度范围
if 150 <= height <= 250:
    confidence *= 1.0  # 标准高度

# 因素4: 名称长度
if 4 <= name_len <= 20:
    confidence *= 1.0

总置信度 = confidence  # 多个因素相乘
```

### 详情页验证置信度

```python
confidence = 0.0

if is_detail_page:
    confidence += 0.4  # 基础分40%

if has_phone:
    confidence += 0.2  # 有电话20%

if has_address:
    confidence += 0.2  # 有地址20%

if match_expected:
    confidence += 0.2  # 名称匹配20%

总置信度 = confidence
```

---

## 错误处理策略

```
┌──────────────┐
│ 尝试采集商家 │
└──────┬───────┘
       │
       ├─ 点击失败？
       │    └─ 记录错误，继续下一个
       │
       ├─ 未进入详情页？
       │    ├─ stats.wrong_page_count += 1
       │    └─ 返回搜索页，继续
       │
       ├─ 商家名不匹配？
       │    ├─ 输出警告
       │    └─ 仍然提取信息
       │
       └─ 信息提取失败？
            ├─ stats.extraction_errors += 1
            └─ 返回搜索页，继续
```

---

## 性能优化点

1. **并发处理**（未来）
   - 多线程采集（需要多个设备）
   - 异步IO操作

2. **缓存机制**
   - UI层级缓存（避免重复获取）
   - 解析结果缓存

3. **智能等待**
   - 动态调整等待时间
   - 检测页面加载完成

4. **批量操作**
   - 批量保存数据库
   - 批量截图

---

## 可扩展性设计

### 1. 新增城市布局

```python
# merchant_card_locator.py
def _identify_layout_type(self, root):
    # 添加新的布局识别逻辑
    if width_ratio == 0.75:  # 新的布局类型
        return 'medium_width'
```

### 2. 新增信息字段

```python
# smart_collector.py
def _extract_merchant_info(self, xml_content):
    # 添加新的提取逻辑
    website = self._extract_website(full_text)
    wechat = self._extract_wechat(full_text)
```

### 3. 新增页面类型

```python
# page_state_analyzer.py
PAGE_TYPE_PROMOTION = "promotion"  # 促销页

def _identify_page_type(self, root):
    if self._has_promotion_banner(root):
        return self.PAGE_TYPE_PROMOTION
```

---

## 测试策略

### 单元测试

```python
# test_page_analyzer.py
def test_identify_search_result_page():
    analyzer = PageStateAnalyzer()
    result = analyzer.analyze_page(sample_xml)
    assert result['page_type'] == 'search_result'
    assert result['has_merchant_list'] == True
```

### 集成测试

```python
# test_smart_collector.py
def test_full_collection_flow():
    collector = SmartCollector(mock_adb)
    result = collector.collect_from_search_page()
    assert result['success'] == True
    assert len(result['data']) > 0
```

### 回归测试

- 保存真实XML样本
- 定期验证识别准确率
- 监控成功率变化

---

**更新日期**: 2025-01-16
**架构版本**: 1.0
