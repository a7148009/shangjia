# 分类系统说明 - ID绑定与数据完整性

**创建时间**: 2025-01-16
**目的**: 解释分类系统的ID绑定机制和数据完整性保障

---

## 一、ID绑定机制

### 1.1 分类ID是唯一标识

分类系统使用**数据库自增ID**作为分类的唯一标识，而不是分类名称或路径。

```sql
CREATE TABLE categories_tree (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 唯一不变的标识
    name TEXT NOT NULL,                     -- 可以修改
    parent_id INTEGER,                      -- 可以修改
    level INTEGER DEFAULT 0,                -- 会自动更新
    path TEXT NOT NULL UNIQUE,              -- 会自动更新
    table_name TEXT NOT NULL UNIQUE,        -- 会自动更新
    create_time TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES categories_tree(id)
)
```

**关键点**：
- `id` 是唯一标识，**永远不会改变**
- `name`, `path`, `table_name` 都可以修改
- 所有关联关系基于 `id` 而非名称

### 1.2 层级支持

系统支持**5级分类**（实际上是无限级，但建议不超过5级）：

```
餐饮 (level=0)
  └─ 中餐 (level=1)
      └─ 川菜 (level=2)
          └─ 火锅 (level=3)
              └─ 麻辣火锅 (level=4)
```

每个节点都有自己的唯一ID，父子关系通过 `parent_id` 关联。

---

## 二、分类重命名机制

### 2.1 重命名操作流程

当重命名一个分类时（例如 "鲜花" → "青羊区"），系统执行以下操作：

```python
def update_category(category_id, new_name):
    # 1. 获取当前分类信息
    old_name, parent_id, level, old_path, old_table_name = get_category(category_id)

    # 2. 计算新路径
    new_path = calculate_new_path(parent_id, new_name)
    new_table_name = f"merchants_{new_path.replace('/', '_')}"

    # 3. 更新分类信息（ID不变！）
    UPDATE categories_tree
    SET name = new_name, path = new_path, table_name = new_table_name
    WHERE id = category_id

    # 4. 重命名商家表（数据完整保留！）
    ALTER TABLE old_table_name RENAME TO new_table_name

    # 5. 更新关联表引用
    UPDATE phones SET table_name = new_table_name WHERE table_name = old_table_name
    UPDATE images SET table_name = new_table_name WHERE table_name = old_table_name

    # 6. 递归更新所有子孙分类的路径
    update_descendant_paths(category_id, old_path, new_path)
```

### 2.2 数据完整性保障

**重要**：`ALTER TABLE ... RENAME TO ...` 操作会**完整保留**表中的所有数据！

示例：
```
重命名前：
  - 分类ID: 2
  - 分类名称: 鲜花
  - 路径: 昆明/鲜花
  - 表名: merchants_昆明_鲜花
  - 表中数据: 50条商家记录

重命名后：
  - 分类ID: 2 (不变！)
  - 分类名称: 青羊区
  - 路径: 昆明/青羊区
  - 表名: merchants_昆明_青羊区
  - 表中数据: 50条商家记录 (完全保留！)
```

### 2.3 子分类路径级联更新

如果重命名的分类下有子分类，所有子孙分类的路径会自动更新：

```
重命名 "餐饮" → "美食"：

更新前：
  餐饮 (ID=1)
    └─ 中餐 (ID=2, path="餐饮/中餐")
        └─ 川菜 (ID=3, path="餐饮/中餐/川菜")

更新后：
  美食 (ID=1, path="美食")
    └─ 中餐 (ID=2, path="美食/中餐")
        └─ 川菜 (ID=3, path="美食/中餐/川菜")

所有ID不变，所有数据完整保留！
```

---

## 三、关于"鲜花"数据的说明

### 3.1 数据库检查结果

检查数据库发现：
```
分类信息：
  ID=1, 名称=昆明, 路径=昆明, 商家数量=0
  ID=2, 名称=鲜花, 路径=昆明/鲜花, 商家数量=0
  ID=3, 名称=成都, 路径=成都, 商家数量=0
  ID=4, 名称=青羊区, 路径=成都/青羊区, 商家数量=0
  ID=5, 名称=金牛区, 路径=成都/金牛区, 商家数量=0
```

### 3.2 结论

1. **"鲜花"分类仍然存在**：ID=2, 路径="昆明/鲜花"
2. **"青羊区"是另一个分类**：ID=4, 路径="成都/青羊区"
3. **所有分类商家数量为0**：说明系统还未采集数据，或之前采集的数据已被清空

**用户误解原因**：
- "鲜花" 和 "青羊区" 是两个不同的分类（不同的ID）
- 如果之前"鲜花"下有数据，现在数据为0，可能是：
  - 从未采集过"鲜花"分类的数据
  - 之前采集的数据被手动删除了
  - 数据库被重置过

### 3.3 验证方法

可以通过数据查看器验证：
1. 打开 `data_viewer.py`
2. 查看左侧分类树
3. 点击 "昆明/鲜花" 分类
4. 右侧表格会显示该分类下的商家数据

---

## 四、数据安全保障

### 4.1 删除保护

系统提供多重删除保护：

1. **子分类检查**：有子分类时不能删除
2. **数据检查**：有商家数据时会提示是否删除
3. **确认对话框**：删除前必须确认

### 4.2 ID绑定的优势

使用ID绑定而非名称绑定的优势：

| 操作 | ID绑定系统 | 名称绑定系统 |
|------|-----------|--------------|
| 重命名分类 | ✅ 数据完整保留 | ❌ 数据丢失或混乱 |
| 移动分类 | ✅ 数据自动跟随 | ❌ 需要手动迁移 |
| 查询效率 | ✅ 整数比较快速 | ❌ 字符串比较慢 |
| 路径变化 | ✅ 自动级联更新 | ❌ 需要重新关联 |
| 唯一性 | ✅ 数据库自动保证 | ❌ 需要手动检查 |

---

## 五、最佳实践建议

### 5.1 分类命名规范

- 使用清晰明确的名称
- 避免使用特殊字符（会影响表名生成）
- 同级分类名称不重复

### 5.2 数据采集建议

1. 先创建完整的分类树结构
2. 再进行数据采集
3. 定期备份数据库文件 `merchants.db`

### 5.3 重命名注意事项

- 重命名分类后，旧的路径名称不再有效
- 在主窗口的分类选择器中需要重新选择分类
- 已采集的数据会自动关联到新名称

---

## 六、技术细节

### 6.1 表名生成规则

```python
def get_table_name(path: str) -> str:
    """
    路径: "餐饮/中餐/川菜"
    表名: "merchants_餐饮_中餐_川菜"
    """
    safe_path = path.replace('/', '_').replace(' ', '_').lower()
    return f"merchants_{safe_path}"
```

### 6.2 关联表结构

**phones表**（电话记录）：
```sql
CREATE TABLE phones (
    id INTEGER PRIMARY KEY,
    merchant_id INTEGER NOT NULL,     -- 商家ID
    table_name TEXT NOT NULL,         -- 所属分类表名
    phone TEXT NOT NULL
)
```

**images表**（图片记录）：
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    merchant_id INTEGER NOT NULL,     -- 商家ID
    table_name TEXT NOT NULL,         -- 所属分类表名
    image_path TEXT NOT NULL
)
```

**关键点**：
- `merchant_id` 在各分类表内唯一
- `table_name` 用于区分不同分类的商家
- 重命名时 `table_name` 会自动更新

---

## 七、总结

1. ✅ **分类系统使用ID绑定**，ID永远不变
2. ✅ **支持5级分类层级**，理论上无限级
3. ✅ **重命名不会丢失数据**，所有数据完整保留
4. ✅ **子分类路径自动更新**，无需手动操作
5. ✅ **关联表引用自动同步**，数据完整性有保障

**用户反馈的数据"消失"问题分析**：
- "鲜花"分类仍然存在（ID=2）
- "青羊区"是另一个分类（ID=4）
- 两者没有重命名关系
- 所有分类商家数量为0，说明未采集数据或数据已清空

**建议**：
- 使用数据查看器确认分类和数据
- 如需重命名，放心操作，数据不会丢失
- 定期备份 `merchants.db` 文件
