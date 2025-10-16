"""
数据库管理模块
用于管理商家信息的SQLite数据库
"""
import sqlite3
import os
import re
from datetime import datetime
from typing import List, Dict, Optional


class DatabaseManager:
    """数据库管理类"""

    def __init__(self, db_path: str = "merchant_data.db"):
        """初始化数据库连接"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.init_database()

    @staticmethod
    def sanitize_table_name(category_name: str) -> str:
        """
        将分类名称转换为安全的表名

        处理规则：
        1. 移除或替换特殊字符（/, \\, -, 等）
        2. 空格替换为下划线
        3. 转换为小写
        4. 只保留字母、数字和下划线

        Args:
            category_name: 分类名称（如 "昆明/鲜花"）

        Returns:
            安全的表名（如 "merchants_kunming_xianhua"）
        """
        # 替换常见分隔符为下划线
        safe_name = category_name.replace('/', '_').replace('\\', '_').replace('-', '_')
        safe_name = safe_name.replace(' ', '_')

        # 只保留字母、数字、下划线和中文字符
        # 使用正则表达式移除其他特殊字符
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]+', '_', safe_name)

        # 移除开头和结尾的下划线
        safe_name = safe_name.strip('_')

        # 转换为小写
        safe_name = safe_name.lower()

        # 添加表名前缀
        return f"merchants_{safe_name}"

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def init_database(self):
        """初始化数据库，创建必要的表"""
        self.connect()

        # 创建分类表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')

        # 创建商家信息表模板（会为每个分类动态创建）
        # 这里只创建一个默认的merchants表作为参考
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT,
                category_id INTEGER,
                collect_time TEXT NOT NULL,
                rating REAL,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')

        # 创建电话号码表（一个商家可能有多个电话）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                phone_number TEXT NOT NULL,
                table_name TEXT NOT NULL,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id)
            )
        ''')

        # 创建图片表（一个商家可能有多张图片）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                image_url TEXT,
                table_name TEXT NOT NULL,
                downloaded_at TEXT NOT NULL,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id)
            )
        ''')

        self.conn.commit()
        self.close()

    def create_category_table(self, category_name: str) -> str:
        """
        为指定分类创建商家表

        Args:
            category_name: 分类名称（如 "昆明/鲜花"）

        Returns:
            安全的表名（如 "merchants_kunming_xianhua"）
        """
        self.connect()

        # 先在分类表中插入分类
        try:
            self.cursor.execute(
                'INSERT INTO categories (name, created_at) VALUES (?, ?)',
                (category_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # 分类已存在
            pass

        # 创建分类对应的商家表（使用安全的表名）
        table_name = self.sanitize_table_name(category_name)

        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT,
                collect_time TEXT NOT NULL
            )
        ''')

        self.conn.commit()
        self.close()

        return table_name

    def insert_merchant(self, table_name: str, merchant_data: Dict) -> int:
        """
        插入商家信息

        Args:
            table_name: 表名
            merchant_data: 商家数据字典，包含name, address, rating等

        Returns:
            插入的商家ID
        """
        self.connect()

        # 插入商家基本信息
        self.cursor.execute(f'''
            INSERT INTO {table_name} (name, address, collect_time)
            VALUES (?, ?, ?)
        ''', (
            merchant_data.get('name', ''),
            merchant_data.get('address', ''),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        merchant_id = self.cursor.lastrowid

        # 插入电话号码
        phones = merchant_data.get('phones', [])
        for phone in phones:
            self.cursor.execute('''
                INSERT INTO phones (merchant_id, phone_number, table_name)
                VALUES (?, ?, ?)
            ''', (merchant_id, phone, table_name))

        # 插入图片信息
        images = merchant_data.get('images', [])
        for img in images:
            self.cursor.execute('''
                INSERT INTO images (merchant_id, image_path, image_url, table_name, downloaded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                merchant_id,
                img.get('path', ''),
                img.get('url', ''),
                table_name,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

        self.conn.commit()
        self.close()

        return merchant_id

    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        self.connect()
        self.cursor.execute('SELECT name FROM categories ORDER BY created_at DESC')
        categories = [row[0] for row in self.cursor.fetchall()]
        self.close()
        return categories

    def get_merchants_by_category(self, category_name: str) -> List[Dict]:
        """
        根据分类获取商家列表

        Args:
            category_name: 分类名称（如 "昆明/鲜花"）

        Returns:
            商家列表
        """
        table_name = self.sanitize_table_name(category_name)
        self.connect()

        try:
            self.cursor.execute(f'SELECT * FROM {table_name}')
            merchants = []
            for row in self.cursor.fetchall():
                merchant_id = row[0]

                # 获取电话号码
                self.cursor.execute(
                    'SELECT phone_number FROM phones WHERE merchant_id = ? AND table_name = ?',
                    (merchant_id, table_name)
                )
                phones = [p[0] for p in self.cursor.fetchall()]

                # 获取图片
                self.cursor.execute(
                    'SELECT image_path, image_url FROM images WHERE merchant_id = ? AND table_name = ?',
                    (merchant_id, table_name)
                )
                images = [{'path': img[0], 'url': img[1]} for img in self.cursor.fetchall()]

                merchants.append({
                    'id': row[0],
                    'name': row[1],
                    'address': row[2],
                    'collect_time': row[3],
                    'phones': phones,
                    'images': images
                })

            self.close()
            return merchants
        except sqlite3.OperationalError:
            self.close()
            return []

    def merchant_exists(self, table_name: str, name: str, address: str) -> bool:
        """
        检查商家是否已存在（通过名称和地址判断）

        Args:
            table_name: 表名
            name: 商家名称
            address: 商家地址

        Returns:
            是否存在
        """
        self.connect()

        try:
            self.cursor.execute(
                f'SELECT COUNT(*) FROM {table_name} WHERE name = ? AND address = ?',
                (name, address)
            )
            count = self.cursor.fetchone()[0]
            self.close()
            return count > 0
        except sqlite3.OperationalError:
            self.close()
            return False

    def delete_merchant(self, table_name: str, merchant_id: int) -> bool:
        """
        删除商家及其关联的电话和图片记录

        Args:
            table_name: 表名
            merchant_id: 商家ID

        Returns:
            是否删除成功
        """
        self.connect()

        try:
            # 删除商家记录
            self.cursor.execute(f'DELETE FROM {table_name} WHERE id = ?', (merchant_id,))

            # 删除电话记录
            self.cursor.execute(
                'DELETE FROM phones WHERE merchant_id = ? AND table_name = ?',
                (merchant_id, table_name)
            )

            # 删除图片记录
            self.cursor.execute(
                'DELETE FROM images WHERE merchant_id = ? AND table_name = ?',
                (merchant_id, table_name)
            )

            self.conn.commit()
            self.close()
            return True

        except Exception as e:
            print(f"删除商家失败: {e}")
            self.close()
            return False
