"""
种子脚本：初始化 Demo API 数据

用途：
- 创建数据库表（通过 Django migration）
- 插入示例商品数据
- 可选：将 API 文档注册到知识库
"""
import os
import sys
import django

# 确保能找到 backend 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from demo_api.models import Product


def seed_products():
    """插入示例商品数据"""
    products = [
        {"name": "机械键盘 K8 Pro", "price": 499.00, "stock": 200, "category": "电子产品", "description": "87键 热插拔 三模无线"},
        {"name": "无线鼠标 M5", "price": 199.00, "stock": 500, "category": "电子产品", "description": "人体工学 静音按键 双模"},
        {"name": "27寸 4K显示器", "price": 2999.00, "stock": 50, "category": "电子产品", "description": "IPS面板 Type-C 65W反向充电"},
        {"name": "Python编程：从入门到实践", "price": 89.00, "stock": 300, "category": "图书", "description": "第3版 全彩印刷"},
        {"name": "测试驱动开发", "price": 69.00, "stock": 150, "category": "图书", "description": "Kent Beck 经典著作"},
        {"name": "办公椅 Ergo Pro", "price": 1299.00, "stock": 80, "category": "家具", "description": "人体工学 腰部支撑 透气网布"},
        {"name": "站立办公升降桌", "price": 2499.00, "stock": 30, "category": "家具", "description": "电动升降 记忆高度 1.2m×0.6m"},
        {"name": "Type-C 数据线 1m", "price": 29.90, "stock": 1000, "category": "配件", "description": "100W快充 编织线 数据传输"},
        {"name": "氮化镓充电器 65W", "price": 99.00, "stock": 400, "category": "配件", "description": "双口GaN 兼容PD/QC协议"},
        {"name": "蓝牙耳机 TWS Pro", "price": 399.00, "stock": 250, "category": "电子产品", "description": "主动降噪 30小时续航 IPX5防水"},
    ]

    created = 0
    for p in products:
        obj, is_new = Product.objects.get_or_create(
            name=p["name"],
            defaults=p,
        )
        if is_new:
            created += 1

    print(f"✅ Demo API 种子数据：{created} 条新商品，共 {Product.objects.count()} 条")
    return created


if __name__ == "__main__":
    seed_products()
