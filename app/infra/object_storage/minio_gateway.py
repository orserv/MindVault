# 引入现有功能，进行汇总
from minio import Minio

from app.shared.clients.minio_utils import get_minio_client
from app.infra.config.providers import infra_config


class MinIOGateway:
    """
    MinIO 对象存储网关类
    统一封装 MinIO 客户端获取、配置读取、图片URL拼接等能力，
    供全项目统一调用，避免到处写配置、重复拼接URL
    """

    # 提供获取桶名称的函数
    @property
    def bucket_name(self) -> str:
        """获取 MinIO 存储桶名称（从全局配置读取）"""
        return infra_config.minio_config.bucket_name

    # 提供获取图片目录名称的函数
    @property
    def mimo_image_dir(self) -> str:
        """获取 MinIO 中存放图片的目录路径（从全局配置读取）"""
        return infra_config.minio_config.minio_img_dir

    # 提供获取 minio_client 的函数
    @property
    def mimo_client(self) -> Minio:
        """获取 MinIO 客户端实例，用于上传、下载、查询文件等操作"""
        return get_minio_client()

    # minio上次文件不会返回访问地址，拼接访问地址 http/https 断点 桶 对象名
    # 提供生成图片URL的函数
    def build_image_url(self, stem: str, image_name: str) -> str:
        """
        拼接生成 MinIO 图片的可访问URL（HTTP/HTTPS）
        :param stem: 文档名称（不带后缀），用于区分不同文档的图片
        :param image_name: 图片原始文件名
        :return: 可直接访问的 MinIO 图片完整URL
        """
        # 根据配置决定使用 http 还是 https
        protocol = "https" if infra_config.minio_config.minio_secure else "http"
        # 拼接最终可访问的图片在线地址
        obj_url = f"{protocol}://{infra_config.minio_config.endpoint}/{self.bucket_name}{self.mimo_image_dir}/{stem}/{image_name}"
        return obj_url


# 创建全局唯一的 MinIO 网关实例，全项目复用
minio_gateway = MinIOGateway()
