"""
分类树形管理模块
支持层级分类的增删改查操作
"""
import sqlite3
from typing import List, Optional, Dict, Tuple
from pathlib import Path


class CategoryNode:
    """分类节点类"""
    def __init__(self, id: int, name: str, parent_id: Optional[int] = None,
                 level: int = 0, path: str = ""):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.level = level
        self.path = path  # 完整路径，如: "餐饮/中餐/川菜"
        self.children: List['CategoryNode'] = []

    def add_child(self, child: 'CategoryNode'):
        """添加子节点"""
        self.children.append(child)

    def get_full_path(self) -> str:
        """获取完整路径"""
        return self.path

    def get_table_name(self) -> str:
        """获取对应的数据库表名"""
        # 使用完整路径生成唯一表名
        safe_path = self.path.replace('/', '_').replace(' ', '_').lower()
        return f"merchants_{safe_path}"


class CategoryManager:
    """分类管理器"""

    def __init__(self, db_path: str = "merchants.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_category_table()

    def _init_category_table(self):
        """初始化分类表"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories_tree (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                level INTEGER DEFAULT 0,
                path TEXT NOT NULL UNIQUE,
                table_name TEXT NOT NULL UNIQUE,
                create_time TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES categories_tree(id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def add_category(self, name: str, parent_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """
        添加分类
        返回: (成功与否, 消息, 新分类ID)
        """
        try:
            # 检查同级是否已存在同名分类
            if parent_id:
                self.cursor.execute('''
                    SELECT id FROM categories_tree
                    WHERE name = ? AND parent_id = ?
                ''', (name, parent_id))
            else:
                self.cursor.execute('''
                    SELECT id FROM categories_tree
                    WHERE name = ? AND parent_id IS NULL
                ''', (name,))

            if self.cursor.fetchone():
                return False, "同级分类中已存在相同名称", None

            # 计算层级和路径
            level = 0
            path = name
            if parent_id:
                self.cursor.execute('''
                    SELECT level, path FROM categories_tree WHERE id = ?
                ''', (parent_id,))
                result = self.cursor.fetchone()
                if result:
                    level = result[0] + 1
                    path = f"{result[1]}/{name}"

            # 生成表名
            table_name = f"merchants_{path.replace('/', '_').replace(' ', '_').lower()}"

            # 插入分类
            from datetime import datetime
            self.cursor.execute('''
                INSERT INTO categories_tree (name, parent_id, level, path, table_name, create_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, parent_id, level, path, table_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            new_id = self.cursor.lastrowid

            # 创建对应的商家表
            self._create_merchant_table(table_name)

            self.conn.commit()
            return True, "分类添加成功", new_id

        except Exception as e:
            self.conn.rollback()
            return False, f"添加失败: {str(e)}", None

    def _create_merchant_table(self, table_name: str):
        """创建商家表"""
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT,
                collect_time TEXT NOT NULL
            )
        ''')

        # 创建电话表（如果不存在）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
            )
        ''')

        # 创建图片表（如果不存在）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                image_path TEXT NOT NULL,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
            )
        ''')

    def delete_category(self, category_id: int, delete_data: bool = False) -> Tuple[bool, str]:
        """
        删除分类
        delete_data: 是否删除分类下的商家数据
        返回: (成功与否, 消息)
        """
        try:
            # 获取分类信息
            self.cursor.execute('''
                SELECT name, table_name, path FROM categories_tree WHERE id = ?
            ''', (category_id,))
            result = self.cursor.fetchone()
            if not result:
                return False, "分类不存在"

            name, table_name, path = result

            # 检查是否有子分类
            self.cursor.execute('''
                SELECT COUNT(*) FROM categories_tree WHERE parent_id = ?
            ''', (category_id,))
            child_count = self.cursor.fetchone()[0]

            if child_count > 0:
                return False, f"无法删除：分类 '{name}' 下还有 {child_count} 个子分类，请先删除子分类"

            # 检查是否有商家数据
            self.cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
            merchant_count = self.cursor.fetchone()[0]

            if merchant_count > 0 and not delete_data:
                return False, f"分类 '{name}' 下有 {merchant_count} 个商家，请选择是否删除数据"

            # 删除分类记录
            self.cursor.execute('DELETE FROM categories_tree WHERE id = ?', (category_id,))

            # 删除商家表
            if delete_data:
                # 删除关联的电话和图片记录
                self.cursor.execute('DELETE FROM phones WHERE table_name = ?', (table_name,))
                self.cursor.execute('DELETE FROM images WHERE table_name = ?', (table_name,))

                # 删除商家表
                self.cursor.execute(f'DROP TABLE IF EXISTS {table_name}')

                # 删除图片文件夹
                from image_manager import ImageManager
                img_manager = ImageManager()
                img_manager.delete_category_images(path)

            self.conn.commit()
            return True, "分类删除成功"

        except Exception as e:
            self.conn.rollback()
            return False, f"删除失败: {str(e)}"

    def update_category(self, category_id: int, new_name: str) -> Tuple[bool, str]:
        """
        更新分类名称
        返回: (成功与否, 消息)
        """
        try:
            # 获取当前分类信息
            self.cursor.execute('''
                SELECT name, parent_id, level, path, table_name FROM categories_tree WHERE id = ?
            ''', (category_id,))
            result = self.cursor.fetchone()
            if not result:
                return False, "分类不存在"

            old_name, parent_id, level, old_path, old_table_name = result

            if old_name == new_name:
                return True, "名称未变化"

            # 检查同级是否已存在同名分类
            if parent_id:
                self.cursor.execute('''
                    SELECT id FROM categories_tree
                    WHERE name = ? AND parent_id = ? AND id != ?
                ''', (new_name, parent_id, category_id))
            else:
                self.cursor.execute('''
                    SELECT id FROM categories_tree
                    WHERE name = ? AND parent_id IS NULL AND id != ?
                ''', (new_name, category_id))

            if self.cursor.fetchone():
                return False, "同级分类中已存在相同名称"

            # 计算新路径
            if parent_id:
                self.cursor.execute('SELECT path FROM categories_tree WHERE id = ?', (parent_id,))
                parent_path = self.cursor.fetchone()[0]
                new_path = f"{parent_path}/{new_name}"
            else:
                new_path = new_name

            new_table_name = f"merchants_{new_path.replace('/', '_').replace(' ', '_').lower()}"

            # 更新分类信息
            self.cursor.execute('''
                UPDATE categories_tree
                SET name = ?, path = ?, table_name = ?
                WHERE id = ?
            ''', (new_name, new_path, new_table_name, category_id))

            # 重命名商家表
            self.cursor.execute(f'ALTER TABLE {old_table_name} RENAME TO {new_table_name}')

            # 更新电话和图片表中的table_name引用
            self.cursor.execute('''
                UPDATE phones SET table_name = ? WHERE table_name = ?
            ''', (new_table_name, old_table_name))

            self.cursor.execute('''
                UPDATE images SET table_name = ? WHERE table_name = ?
            ''', (new_table_name, old_table_name))

            # 更新所有子孙分类的路径
            self._update_descendant_paths(category_id, old_path, new_path)

            self.conn.commit()
            return True, "分类更新成功"

        except Exception as e:
            self.conn.rollback()
            return False, f"更新失败: {str(e)}"

    def _update_descendant_paths(self, category_id: int, old_path: str, new_path: str):
        """递归更新所有子孙分类的路径"""
        self.cursor.execute('''
            SELECT id, path, table_name FROM categories_tree WHERE parent_id = ?
        ''', (category_id,))

        children = self.cursor.fetchall()
        for child_id, child_path, old_table_name in children:
            # 替换路径前缀
            updated_path = child_path.replace(old_path, new_path, 1)
            new_table_name = f"merchants_{updated_path.replace('/', '_').replace(' ', '_').lower()}"

            # 更新子分类
            self.cursor.execute('''
                UPDATE categories_tree
                SET path = ?, table_name = ?
                WHERE id = ?
            ''', (updated_path, new_table_name, child_id))

            # 重命名表
            self.cursor.execute(f'ALTER TABLE {old_table_name} RENAME TO {new_table_name}')

            # 更新电话和图片表中的引用
            self.cursor.execute('UPDATE phones SET table_name = ? WHERE table_name = ?',
                              (new_table_name, old_table_name))
            self.cursor.execute('UPDATE images SET table_name = ? WHERE table_name = ?',
                              (new_table_name, old_table_name))

            # 递归更新子孙
            self._update_descendant_paths(child_id, child_path, updated_path)

    def get_category_tree(self) -> List[CategoryNode]:
        """
        获取完整分类树
        返回根节点列表
        """
        # 获取所有分类
        self.cursor.execute('''
            SELECT id, name, parent_id, level, path
            FROM categories_tree
            ORDER BY level, parent_id, name
        ''')

        all_categories = self.cursor.fetchall()

        # 构建节点字典
        nodes: Dict[int, CategoryNode] = {}
        root_nodes: List[CategoryNode] = []

        for cat_id, name, parent_id, level, path in all_categories:
            node = CategoryNode(cat_id, name, parent_id, level, path)
            nodes[cat_id] = node

            if parent_id is None:
                root_nodes.append(node)
            else:
                if parent_id in nodes:
                    nodes[parent_id].add_child(node)

        return root_nodes

    def get_category_by_id(self, category_id: int) -> Optional[CategoryNode]:
        """根据ID获取分类节点"""
        self.cursor.execute('''
            SELECT id, name, parent_id, level, path
            FROM categories_tree
            WHERE id = ?
        ''', (category_id,))

        result = self.cursor.fetchone()
        if result:
            return CategoryNode(result[0], result[1], result[2], result[3], result[4])
        return None

    def get_all_categories_flat(self) -> List[Dict]:
        """
        获取所有分类（扁平列表）
        返回: [{'id': 1, 'name': '餐饮', 'path': '餐饮', 'level': 0, 'table_name': 'merchants_餐饮'}, ...]
        """
        self.cursor.execute('''
            SELECT id, name, path, level, table_name, parent_id
            FROM categories_tree
            ORDER BY path
        ''')

        categories = []
        for row in self.cursor.fetchall():
            categories.append({
                'id': row[0],
                'name': row[1],
                'path': row[2],
                'level': row[3],
                'table_name': row[4],
                'parent_id': row[5]
            })

        return categories

    def search_categories(self, keyword: str) -> List[Dict]:
        """
        搜索分类
        返回匹配的分类列表
        """
        self.cursor.execute('''
            SELECT id, name, path, level, table_name
            FROM categories_tree
            WHERE name LIKE ? OR path LIKE ?
            ORDER BY level, name
        ''', (f'%{keyword}%', f'%{keyword}%'))

        categories = []
        for row in self.cursor.fetchall():
            categories.append({
                'id': row[0],
                'name': row[1],
                'path': row[2],
                'level': row[3],
                'table_name': row[4]
            })

        return categories

    def get_merchant_count(self, category_id: int) -> int:
        """获取分类下的商家数量"""
        try:
            # 直接从数据库读取table_name字段（更可靠）
            self.cursor.execute('''
                SELECT table_name FROM categories_tree WHERE id = ?
            ''', (category_id,))
            result = self.cursor.fetchone()
            if not result:
                return 0

            table_name = result[0]

            # 查询该表的商家数量
            self.cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
            return self.cursor.fetchone()[0]
        except Exception as e:
            # 表可能不存在或其他错误
            return 0

    def close(self):
        """关闭数据库连接"""
        self.conn.close()


if __name__ == "__main__":
    # 测试代码
    manager = CategoryManager("test_categories.db")

    # 添加根分类
    success, msg, id1 = manager.add_category("餐饮")
    print(f"添加餐饮: {msg}, ID: {id1}")

    success, msg, id2 = manager.add_category("鲜花")
    print(f"添加鲜花: {msg}, ID: {id2}")

    # 添加子分类
    if id1:
        success, msg, id3 = manager.add_category("中餐", id1)
        print(f"添加中餐: {msg}, ID: {id3}")

        if id3:
            success, msg, id4 = manager.add_category("川菜", id3)
            print(f"添加川菜: {msg}, ID: {id4}")

    # 获取分类树
    print("\n分类树:")
    def print_tree(nodes, indent=0):
        for node in nodes:
            print("  " * indent + f"- {node.name} (ID: {node.id}, Path: {node.path})")
            print_tree(node.children, indent + 1)

    tree = manager.get_category_tree()
    print_tree(tree)

    # 搜索
    print("\n搜索 '中':")
    results = manager.search_categories("中")
    for r in results:
        print(f"  {r['path']}")

    manager.close()
