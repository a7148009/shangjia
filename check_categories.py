"""临时脚本：检查数据库中的分类和数据"""
import sqlite3

conn = sqlite3.connect('merchants.db')
cursor = conn.cursor()

print("=" * 60)
print("分类信息:")
print("=" * 60)
cursor.execute('SELECT id, name, path, table_name FROM categories_tree ORDER BY id')
for row in cursor.fetchall():
    cat_id, name, path, table_name = row
    print(f"ID={cat_id}, 名称={name}, 路径={path}")
    print(f"  表名={table_name}")

    # 检查该表的商家数量
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f"  商家数量: {count}")

        if count > 0:
            cursor.execute(f'SELECT name FROM {table_name} LIMIT 5')
            merchants = cursor.fetchall()
            print(f"  示例商家: {', '.join([m[0] for m in merchants])}")
    except Exception as e:
        print(f"  错误: {e}")

    print()

print("=" * 60)
print("数据库中的所有商家表:")
print("=" * 60)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'merchants_%' ORDER BY name")
for row in cursor.fetchall():
    table_name = row[0]
    cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    count = cursor.fetchone()[0]
    print(f"{table_name}: {count} 条记录")

conn.close()
