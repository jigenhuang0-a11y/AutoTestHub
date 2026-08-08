from rest_framework import serializers
from .models import KnowledgeBase, Document, ChatMessage


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    """知识库序列化器"""
    document_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = KnowledgeBase
        fields = ['id', 'name', 'description', 'document_count', 'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_document_count(self, obj):
        return obj.documents.count()

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class DocumentSerializer(serializers.ModelSerializer):
    """文档序列化器"""
    knowledge_base_name = serializers.CharField(source='knowledge_base.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'knowledge_base', 'knowledge_base_name', 'title', 'file_path', 'file_type', 'file_size', 'chunk_count', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']
        read_only_fields = ['uploaded_by', 'uploaded_at', 'chunk_count']


class ChatMessageSerializer(serializers.ModelSerializer):
    """对话消息序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'knowledge_base', 'session_id', 'mode', 'question', 'answer', 'context_docs', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['created_by', 'created_at']
