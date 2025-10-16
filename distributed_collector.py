"""
分布式商家采集架构实现
支持单机多设备和多机多设备场景
"""
import os
import json
import time
import uuid
import redis
import threading
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from queue import Queue
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DistributedCollectorConfig:
    """分布式采集配置"""

    def __init__(self):
        # 机器标识（每台电脑唯一）
        self.machine_id = os.environ.get('MACHINE_ID', f"machine_{uuid.uuid4().hex[:8]}")

        # 模式：'local'本地SQLite, 'redis'消息队列, 'direct'直连数据库
        self.mode = os.environ.get('COLLECTOR_MODE', 'local')

        # Redis配置（消息队列模式）
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', 6379))
        self.redis_queue = 'merchant_queue'

        # MySQL配置（直连模式）
        self.mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
        self.mysql_port = int(os.environ.get('MYSQL_PORT', 3306))
        self.mysql_user = os.environ.get('MYSQL_USER', 'root')
        self.mysql_pass = os.environ.get('MYSQL_PASS', '')
        self.mysql_db = os.environ.get('MYSQL_DB', 'merchants_db')

        # 并发配置
        self.max_workers = int(os.environ.get('MAX_WORKERS', 10))
        self.batch_size = int(os.environ.get('BATCH_SIZE', 50))


class LocalCollector:
    """本地SQLite模式（单机多设备）"""

    def __init__(self, config: DistributedCollectorConfig):
        self.config = config
        self.db_lock = threading.Lock()

        # 导入现有的数据库管理器
        from database import DatabaseManager
        self.db = DatabaseManager()

        logger.info(f"[{config.machine_id}] 本地模式已启动")

    def save_merchant(self, merchant_data: Dict, device_id: str):
        """线程安全的本地保存"""
        with self.db_lock:
            # 添加机器和设备标识
            merchant_data['machine_id'] = self.config.machine_id
            merchant_data['device_id'] = device_id

            # 使用现有的数据库方法
            self.db.add_merchant(
                category_path=merchant_data.get('category_name', 'unknown'),
                merchant_data=merchant_data
            )

            logger.info(f"[{self.config.machine_id}][{device_id}] 保存商家: {merchant_data['name']}")


class RedisQueueCollector:
    """Redis队列模式（多机多设备）"""

    def __init__(self, config: DistributedCollectorConfig):
        self.config = config
        self.redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=0,
            decode_responses=False  # 保持字节格式
        )

        # 测试连接
        try:
            self.redis_client.ping()
            logger.info(f"[{config.machine_id}] Redis队列模式已启动: {config.redis_host}:{config.redis_port}")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise

    def save_merchant(self, merchant_data: Dict, device_id: str):
        """推送到Redis队列"""
        # 添加元数据
        merchant_data['machine_id'] = self.config.machine_id
        merchant_data['device_id'] = device_id
        merchant_data['enqueue_time'] = time.time()

        # 序列化并推送
        data_json = json.dumps(merchant_data, ensure_ascii=False)
        self.redis_client.lpush(self.config.redis_queue, data_json)

        logger.debug(f"[{self.config.machine_id}][{device_id}] 推送到队列: {merchant_data['name']}")


class DirectDatabaseCollector:
    """直连数据库模式（多机多设备）"""

    def __init__(self, config: DistributedCollectorConfig):
        self.config = config

        # 创建连接池
        db_url = (
            f"mysql+pymysql://{config.mysql_user}:{config.mysql_pass}"
            f"@{config.mysql_host}:{config.mysql_port}/{config.mysql_db}"
            f"?charset=utf8mb4"
        )

        self.engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=20,           # 基础连接数
            max_overflow=30,        # 最多50个连接
            pool_timeout=30,
            pool_recycle=3600,      # 1小时回收
            pool_pre_ping=True,     # 连接前测试
            echo=False
        )

        logger.info(f"[{config.machine_id}] 数据库直连模式已启动: {config.mysql_host}")

        # 批量写入缓冲
        self.write_buffer = Queue(maxsize=1000)
        self.batch_size = config.batch_size

        # 启动后台批量写入线程
        self.running = True
        self.batch_writer_thread = threading.Thread(target=self._batch_writer, daemon=True)
        self.batch_writer_thread.start()

    def save_merchant(self, merchant_data: Dict, device_id: str):
        """添加到写入缓冲"""
        merchant_data['machine_id'] = self.config.machine_id
        merchant_data['device_id'] = device_id

        self.write_buffer.put(merchant_data)

    def _batch_writer(self):
        """后台批量写入线程"""
        batch = []

        while self.running:
            try:
                # 收集一批数据
                while len(batch) < self.batch_size:
                    try:
                        data = self.write_buffer.get(timeout=2)
                        batch.append(data)
                    except:
                        break  # 超时，处理当前批次

                # 批量写入
                if batch:
                    self._flush_batch(batch)
                    batch = []

            except Exception as e:
                logger.error(f"批量写入失败: {e}")
                time.sleep(1)

    def _flush_batch(self, batch: List[Dict]):
        """批量插入数据库"""
        if not batch:
            return

        try:
            with self.engine.begin() as conn:
                # 构造批量插入SQL
                sql = text("""
                    INSERT INTO merchants
                    (name, address, phones, category_name, machine_id, device_id, collect_time)
                    VALUES
                    (:name, :address, :phones, :category_name, :machine_id, :device_id, :collect_time)
                    ON DUPLICATE KEY UPDATE
                    collect_time = VALUES(collect_time)
                """)

                # 准备数据
                values = []
                for merchant in batch:
                    values.append({
                        'name': merchant['name'],
                        'address': merchant.get('address', ''),
                        'phones': json.dumps(merchant.get('phones', []), ensure_ascii=False),
                        'category_name': merchant.get('category_name', ''),
                        'machine_id': merchant.get('machine_id', ''),
                        'device_id': merchant.get('device_id', ''),
                        'collect_time': merchant.get('collection_time', time.strftime('%Y-%m-%d %H:%M:%S'))
                    })

                # 批量执行
                conn.execute(sql, values)

                logger.info(f"[{self.config.machine_id}] 批量写入 {len(batch)} 条数据")

        except Exception as e:
            logger.error(f"批量写入数据库失败: {e}")
            # 失败数据可以写入本地日志待重试
            with open(f'failed_batch_{int(time.time())}.json', 'w', encoding='utf-8') as f:
                json.dump(batch, f, ensure_ascii=False, indent=2)

    def close(self):
        """关闭连接"""
        self.running = False
        self.batch_writer_thread.join(timeout=10)

        # 清空缓冲区
        remaining = []
        while not self.write_buffer.empty():
            remaining.append(self.write_buffer.get())
        if remaining:
            self._flush_batch(remaining)

        self.engine.dispose()


class MultiDeviceCollector:
    """多设备协调器"""

    def __init__(self, config: DistributedCollectorConfig):
        self.config = config

        # 根据模式选择存储后端
        if config.mode == 'local':
            self.storage = LocalCollector(config)
        elif config.mode == 'redis':
            self.storage = RedisQueueCollector(config)
        elif config.mode == 'direct':
            self.storage = DirectDatabaseCollector(config)
        else:
            raise ValueError(f"未知模式: {config.mode}")

        logger.info(f"[{config.machine_id}] 多设备采集器已初始化，模式: {config.mode}")

    def collect_from_device(self, device_serial: str, category_name: str, max_merchants: int = 100):
        """单个设备的采集任务"""
        from adb_manager import ADBDeviceManager
        from merchant_collector import MerchantCollector

        try:
            logger.info(f"[{self.config.machine_id}][{device_serial}] 开始采集 {category_name}")

            # 连接设备
            adb = ADBDeviceManager(device_serial=device_serial)
            collector = MerchantCollector(adb)

            # 执行采集
            merchants = collector.collect_all_merchants_in_category(
                category_name=category_name,
                max_merchants=max_merchants
            )

            # 保存数据
            for merchant in merchants:
                self.storage.save_merchant(merchant, device_serial)

            logger.info(f"[{self.config.machine_id}][{device_serial}] 完成采集: {len(merchants)} 个商家")

            return {
                'device': device_serial,
                'category': category_name,
                'count': len(merchants),
                'status': 'success'
            }

        except Exception as e:
            logger.error(f"[{self.config.machine_id}][{device_serial}] 采集失败: {e}")
            return {
                'device': device_serial,
                'category': category_name,
                'count': 0,
                'status': 'failed',
                'error': str(e)
            }

    def run_parallel_collection(self, tasks: List[Dict]):
        """
        并行采集多个任务

        Args:
            tasks: 任务列表，每个任务包含 {'device': 'xxx', 'category': 'xxx', 'max': 100}
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(
                    self.collect_from_device,
                    task['device'],
                    task['category'],
                    task.get('max', 100)
                ): task
                for task in tasks
            }

            # 等待完成
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"任务失败: {task}, 错误: {e}")
                    results.append({
                        'device': task['device'],
                        'category': task['category'],
                        'count': 0,
                        'status': 'error',
                        'error': str(e)
                    })

        return results

    def close(self):
        """关闭资源"""
        if hasattr(self.storage, 'close'):
            self.storage.close()


# ==================== 消费者服务（独立进程） ====================

class RedisConsumer:
    """Redis队列消费者（独立部署）"""

    def __init__(self, config: DistributedCollectorConfig):
        self.config = config
        self.redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=0,
            decode_responses=False
        )

        # 数据库连接
        self.storage = DirectDatabaseCollector(config)

        logger.info(f"消费者已启动: {config.machine_id}")

    def run(self):
        """持续消费队列"""
        logger.info("开始监听队列...")

        while True:
            try:
                # 阻塞式获取（5秒超时）
                result = self.redis_client.brpop(self.config.redis_queue, timeout=5)

                if result:
                    _, data = result
                    merchant = json.loads(data)

                    # 写入数据库
                    self.storage.save_merchant(merchant, merchant.get('device_id', 'unknown'))

            except KeyboardInterrupt:
                logger.info("收到停止信号")
                break
            except Exception as e:
                logger.error(f"消费失败: {e}")
                time.sleep(1)

        self.storage.close()


# ==================== 使用示例 ====================

def example_single_machine_multi_device():
    """示例：单机10部手机"""
    config = DistributedCollectorConfig()
    config.mode = 'local'  # 本地SQLite
    config.max_workers = 10

    collector = MultiDeviceCollector(config)

    # 定义任务
    tasks = [
        {'device': f'device_{i}', 'category': '昆明_鲜花', 'max': 50}
        for i in range(10)
    ]

    # 并行采集
    results = collector.run_parallel_collection(tasks)

    # 打印结果
    for result in results:
        print(f"{result['device']}: {result['count']} 个商家 ({result['status']})")

    collector.close()


def example_multi_machine_redis_queue():
    """示例：多机Redis队列模式"""
    config = DistributedCollectorConfig()
    config.mode = 'redis'
    config.redis_host = 'your-redis-server.com'
    config.max_workers = 10

    collector = MultiDeviceCollector(config)

    # 每台电脑执行类似的任务
    tasks = [
        {'device': f'{config.machine_id}_device_{i}', 'category': '成都_鲜花', 'max': 100}
        for i in range(10)
    ]

    results = collector.run_parallel_collection(tasks)
    collector.close()


def example_consumer_service():
    """示例：消费者服务（独立运行）"""
    config = DistributedCollectorConfig()
    config.redis_host = 'your-redis-server.com'
    config.mysql_host = 'your-mysql-server.com'
    config.mysql_user = 'your_user'
    config.mysql_pass = 'your_password'

    consumer = RedisConsumer(config)
    consumer.run()


if __name__ == '__main__':
    # 根据环境变量决定运行模式
    mode = os.environ.get('RUN_MODE', 'collector')

    if mode == 'collector':
        example_single_machine_multi_device()
    elif mode == 'consumer':
        example_consumer_service()
