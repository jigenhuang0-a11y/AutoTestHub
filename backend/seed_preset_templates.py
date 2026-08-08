#!/usr/bin/env python
"""Seed preset templates for data factory module"""
import os
import secrets
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from data_factory.models import PresetTemplate
from django.contrib.auth import get_user_model

User = get_user_model()

# Get or create admin user (password from env or auto-generated)
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    admin_password = os.getenv('ADMIN_PASSWORD', secrets.token_urlsafe(12))
    user = User.objects.create_superuser('admin', 'admin@test.com', admin_password)
    print(f'创建管理员: admin / {admin_password}')

templates_data = [
    {
        'name': '跨境电商订单数据',
        'business_type': 'order',
        'description': '生成包含订单ID、金额、币种、商品信息的完整订单数据,支持边界值测试',
        'field_definitions': [
            {'field': 'order_id', 'type': 'string', 'label': '订单ID', 'required': True, 'faker': 'uuid4'},
            {'field': 'customer_name', 'type': 'string', 'label': '客户姓名', 'required': True, 'faker': 'name'},
            {'field': 'amount', 'type': 'float', 'label': '订单金额', 'required': True, 'faker': 'random_float'},
            {'field': 'currency', 'type': 'string', 'label': '币种', 'required': True, 'faker': 'currency_code'},
            {'field': 'items_count', 'type': 'int', 'label': '商品数量', 'required': True, 'faker': 'random_int'},
            {'field': 'order_time', 'type': 'datetime', 'label': '下单时间', 'required': True, 'faker': 'date_time'},
        ],
        'boundary_rules': {
            'amount': {'min': 0.01, 'max': 999999.99, 'boundary_values': [0, 0.01, -0.01, 999999.99, None]},
            'items_count': {'min': 1, 'max': 999, 'boundary_values': [0, 1, -1, 999, 1000, None]}
        },
        'faker_mappings': {},
        'is_active': True,
        'usage_count': 0
    },
    {
        'name': '国际物流追踪数据',
        'business_type': 'logistics',
        'description': '生成物流单号、运输状态、轨迹信息等物流相关数据',
        'field_definitions': [
            {'field': 'tracking_number', 'type': 'string', 'label': '物流单号', 'required': True},
            {'field': 'carrier', 'type': 'string', 'label': '承运商', 'required': True},
            {'field': 'origin_country', 'type': 'string', 'label': '起始国家', 'required': True},
            {'field': 'destination_country', 'type': 'string', 'label': '目的国家', 'required': True},
            {'field': 'status', 'type': 'string', 'label': '物流状态', 'required': True},
            {'field': 'weight_kg', 'type': 'float', 'label': '重量(kg)', 'required': True},
        ],
        'boundary_rules': {
            'weight_kg': {'min': 0.01, 'max': 1000, 'boundary_values': [0, 0.01, -0.01, 1000, None]},
            'status': {'valid_values': ['pending', 'in_transit', 'delivered', 'returned']}
        },
        'faker_mappings': {},
        'is_active': True,
        'usage_count': 0
    },
    {
        'name': '售后工单数据',
        'business_type': 'after_sales',
        'description': '生成退款申请、退货工单、投诉记录等售后场景数据',
        'field_definitions': [
            {'field': 'ticket_id', 'type': 'string', 'label': '工单ID', 'required': True},
            {'field': 'order_id', 'type': 'string', 'label': '关联订单', 'required': True},
            {'field': 'ticket_type', 'type': 'string', 'label': '工单类型', 'required': True},
            {'field': 'reason', 'type': 'string', 'label': '申请原因', 'required': True},
            {'field': 'refund_amount', 'type': 'float', 'label': '退款金额', 'required': False},
            {'field': 'priority', 'type': 'string', 'label': '优先级', 'required': True},
        ],
        'boundary_rules': {
            'refund_amount': {'min': 0, 'max': 999999.99, 'boundary_values': [0, 0.01, -0.01, None]},
            'ticket_type': {'valid_values': ['refund', 'return', 'exchange', 'complaint']}
        },
        'faker_mappings': {},
        'is_active': True,
        'usage_count': 0
    },
    {
        'name': '商家入驻信息',
        'business_type': 'merchant',
        'description': '生成商家资质、店铺信息、联系方式等商家相关数据',
        'field_definitions': [
            {'field': 'merchant_id', 'type': 'string', 'label': '商家ID', 'required': True},
            {'field': 'shop_name', 'type': 'string', 'label': '店铺名称', 'required': True},
            {'field': 'business_license', 'type': 'string', 'label': '营业执照号', 'required': True},
            {'field': 'contact_email', 'type': 'string', 'label': '联系邮箱', 'required': True},
            {'field': 'contact_phone', 'type': 'string', 'label': '联系电话', 'required': True},
            {'field': 'rating', 'type': 'float', 'label': '店铺评分', 'required': False},
        ],
        'boundary_rules': {
            'rating': {'min': 0, 'max': 5, 'boundary_values': [0, 0.1, -0.1, 5, 5.1, None]},
            'contact_email': {'format': 'email'}
        },
        'faker_mappings': {},
        'is_active': True,
        'usage_count': 0
    }
]

print('Seeding preset templates...')
for template_data in templates_data:
    template, created = PresetTemplate.objects.get_or_create(
        name=template_data['name'],
        defaults={**template_data, 'created_by': user}
    )
    if created:
        print(f'[OK] Created: {template.name} ({template.business_type})')
    else:
        print(f'[SKIP] Already exists: {template.name}')

print(f'\nTotal templates: {PresetTemplate.objects.count()}')
print('Done!')
