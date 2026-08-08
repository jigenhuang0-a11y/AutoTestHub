from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Product
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    商品 CRUD API — 供测试平台验证用

    提供完整的 RESTful 接口：
    - GET    /api/demo/products/        列表
    - POST   /api/demo/products/        创建
    - GET    /api/demo/products/{id}/    详情
    - PUT    /api/demo/products/{id}/    全量更新
    - PATCH  /api/demo/products/{id}/    部分更新
    - DELETE /api/demo/products/{id}/    删除
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]  # Demo API 无需认证

    def create(self, request, *args, **kwargs):
        """创建商品 — 带参数校验"""
        # 必填字段校验
        name = request.data.get('name', '').strip()
        if not name:
            return Response(
                {'error': '商品名称不能为空'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price = request.data.get('price')
        if price is not None:
            try:
                price = float(price)
                if price < 0:
                    return Response(
                        {'error': '价格不能为负数'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (TypeError, ValueError):
                return Response(
                    {'error': '价格格式无效'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        stock = request.data.get('stock', 0)
        if stock is not None:
            try:
                stock = int(stock)
                if stock < 0:
                    return Response(
                        {'error': '库存不能为负数'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (TypeError, ValueError):
                return Response(
                    {'error': '库存格式无效'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """商品列表 — 支持分类筛选"""
        queryset = self.filter_queryset(self.get_queryset())

        # 支持 ?category=xxx 筛选
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__iexact=category)

        # 支持 ?is_active=true/false 筛选
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """删除商品 — 返回 204"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取所有分类列表（去重）"""
        cats = (
            Product.objects
            .filter(is_active=True)
            .values_list('category', flat=True)
            .order_by('category')
            .distinct()
        )
        return Response([c for c in cats if c])

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取商品统计信息"""
        from django.db.models import Count, Sum, Avg
        total = Product.objects.count()
        active = Product.objects.filter(is_active=True).count()
        total_stock = Product.objects.aggregate(s=Sum('stock'))['s'] or 0
        avg_price = Product.objects.filter(is_active=True).aggregate(a=Avg('price'))['a'] or 0
        return Response({
            'total_products': total,
            'active_products': active,
            'total_stock': total_stock,
            'avg_price': round(float(avg_price), 2),
        })
