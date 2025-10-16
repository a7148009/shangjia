"""
图片管理模块
用于下载和存储商家图片
"""
import os
import time
import hashlib
from typing import List, Dict
from PIL import Image
import requests
from io import BytesIO


class ImageManager:
    """图片管理类"""

    def __init__(self, base_dir: str = "merchant_images"):
        """
        初始化图片管理器

        Args:
            base_dir: 图片存储基础目录
        """
        self.base_dir = base_dir
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

    def save_screenshot(self, pil_image, merchant_name: str, category: str, index: int = 0) -> str:
        """
        保存截图

        Args:
            pil_image: PIL Image对象或图片路径
            merchant_name: 商家名称
            category: 分类名称
            index: 图片索引

        Returns:
            保存的文件路径
        """
        try:
            # 创建分类目录
            category_dir = os.path.join(self.base_dir, self._sanitize_filename(category))
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)

            # 创建商家目录
            merchant_dir = os.path.join(category_dir, self._sanitize_filename(merchant_name))
            if not os.path.exists(merchant_dir):
                os.makedirs(merchant_dir)

            # 生成文件名
            timestamp = int(time.time() * 1000)
            filename = f"{merchant_name}_{index}_{timestamp}.png"
            filepath = os.path.join(merchant_dir, self._sanitize_filename(filename))

            # 保存图片
            if isinstance(pil_image, str):
                # 如果是路径，复制文件
                img = Image.open(pil_image)
                img.save(filepath)
            else:
                # 如果是PIL Image对象，直接保存
                pil_image.save(filepath)

            print(f"图片已保存: {filepath}")
            return filepath

        except Exception as e:
            print(f"保存截图失败: {e}")
            return ""

    def download_image(self, url: str, merchant_name: str, category: str, index: int = 0) -> str:
        """
        从URL下载图片

        Args:
            url: 图片URL
            merchant_name: 商家名称
            category: 分类名称
            index: 图片索引

        Returns:
            保存的文件路径
        """
        try:
            # 创建分类目录
            category_dir = os.path.join(self.base_dir, self._sanitize_filename(category))
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)

            # 创建商家目录
            merchant_dir = os.path.join(category_dir, self._sanitize_filename(merchant_name))
            if not os.path.exists(merchant_dir):
                os.makedirs(merchant_dir)

            # 下载图片
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            if response.status_code == 200:
                # 从URL或内容生成文件名
                img_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                timestamp = int(time.time() * 1000)

                # 尝试从响应头获取图片格式
                content_type = response.headers.get('Content-Type', '')
                ext = 'jpg'
                if 'png' in content_type:
                    ext = 'png'
                elif 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'webp' in content_type:
                    ext = 'webp'

                filename = f"{merchant_name}_{index}_{img_hash}_{timestamp}.{ext}"
                filepath = os.path.join(merchant_dir, self._sanitize_filename(filename))

                # 保存图片
                img = Image.open(BytesIO(response.content))
                img.save(filepath)

                print(f"图片已下载: {filepath}")
                return filepath
            else:
                print(f"下载图片失败，状态码: {response.status_code}")
                return ""

        except Exception as e:
            print(f"下载图片失败: {e}")
            return ""

    def save_from_device(self, adb_manager, merchant_name: str, category: str, index: int = 0) -> str:
        """
        从设备截图并保存

        Args:
            adb_manager: ADB设备管理器
            merchant_name: 商家名称
            category: 分类名称
            index: 图片索引

        Returns:
            保存的文件路径
        """
        try:
            # 创建分类目录
            category_dir = os.path.join(self.base_dir, self._sanitize_filename(category))
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)

            # 创建商家目录
            merchant_dir = os.path.join(category_dir, self._sanitize_filename(merchant_name))
            if not os.path.exists(merchant_dir):
                os.makedirs(merchant_dir)

            # 生成文件名
            timestamp = int(time.time() * 1000)
            filename = f"{merchant_name}_{index}_{timestamp}.png"
            filepath = os.path.join(merchant_dir, self._sanitize_filename(filename))

            # 截图并保存
            result = adb_manager.screenshot(filepath)

            if result:
                print(f"截图已保存: {filepath}")
                return filepath
            else:
                print("截图失败")
                return ""

        except Exception as e:
            print(f"从设备保存图片失败: {e}")
            return ""

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符

        Args:
            filename: 原始文件名

        Returns:
            清理后的文件名
        """
        # Windows文件名非法字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

        sanitized = filename
        for char in illegal_chars:
            sanitized = sanitized.replace(char, '_')

        # 限制文件名长度
        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        return sanitized

    def get_merchant_images(self, merchant_name: str, category: str) -> List[str]:
        """
        获取商家的所有图片路径

        Args:
            merchant_name: 商家名称
            category: 分类名称

        Returns:
            图片路径列表
        """
        try:
            merchant_dir = os.path.join(
                self.base_dir,
                self._sanitize_filename(category),
                self._sanitize_filename(merchant_name)
            )

            if not os.path.exists(merchant_dir):
                return []

            images = []
            for filename in os.listdir(merchant_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    images.append(os.path.join(merchant_dir, filename))

            return sorted(images)

        except Exception as e:
            print(f"获取商家图片失败: {e}")
            return []

    def delete_merchant_images(self, merchant_name: str, category: str) -> bool:
        """
        删除商家的所有图片

        Args:
            merchant_name: 商家名称
            category: 分类名称

        Returns:
            是否成功
        """
        try:
            merchant_dir = os.path.join(
                self.base_dir,
                self._sanitize_filename(category),
                self._sanitize_filename(merchant_name)
            )

            if os.path.exists(merchant_dir):
                import shutil
                shutil.rmtree(merchant_dir)
                print(f"已删除商家图片目录: {merchant_dir}")
                return True

            return False

        except Exception as e:
            print(f"删除商家图片失败: {e}")
            return False

    def delete_category_images(self, category_path: str) -> bool:
        """
        删除整个分类的图片文件夹

        Args:
            category_path: 分类路径（如 "餐饮/中餐/川菜"）

        Returns:
            是否成功
        """
        try:
            # 将路径中的 / 替换为操作系统路径分隔符
            category_dir = os.path.join(
                self.base_dir,
                *[self._sanitize_filename(part) for part in category_path.split('/')]
            )

            if os.path.exists(category_dir):
                import shutil
                shutil.rmtree(category_dir)
                print(f"已删除分类图片目录: {category_dir}")
                return True

            return False

        except Exception as e:
            print(f"删除分类图片失败: {e}")
            return False

    def compress_image(self, image_path: str, max_size: int = 1920, quality: int = 85) -> bool:
        """
        压缩图片

        Args:
            image_path: 图片路径
            max_size: 最大尺寸（宽或高）
            quality: 压缩质量 (1-100)

        Returns:
            是否成功
        """
        try:
            img = Image.open(image_path)

            # 计算新尺寸
            width, height = img.size
            if width > max_size or height > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 保存压缩后的图片
            img.save(image_path, quality=quality, optimize=True)
            print(f"图片已压缩: {image_path}")
            return True

        except Exception as e:
            print(f"压缩图片失败: {e}")
            return False
