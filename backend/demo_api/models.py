from django.db import models


class Product(models.Model):
    """商品模型 — 简单的 CRUD 示例"""
    name = models.CharField('商品名称', max_length=200)
    description = models.TextField('商品描述', blank=True, default='')
    price = models.DecimalField('价格', max_digits=10, decimal_places=2)
    stock = models.IntegerField('库存', default=0)
    category = models.CharField('分类', max_length=100, blank=True, default='')
    is_active = models.BooleanField('是否上架', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'demo_products'
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (¥{self.price})"
