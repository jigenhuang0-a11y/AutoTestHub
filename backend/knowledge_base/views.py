import os
import threading
import logging
from pathlib import Path
from django.conf import settings
from django.db import connection, connections
from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import KnowledgeBase, Document, ChatMessage
from .serializers import KnowledgeBaseSerializer, DocumentSerializer, ChatMessageSerializer
from .services import RAGEngine
import json
import uuid

logger = logging.getLogger(__name__)


def _process_document_async(file_path, pk, document_id):
    """后台异步处理文档向量化"""
    try:
        # 确保线程有独立的 DB 连接（Django 标准做法）
        connections.close_all()

        rag_engine = RAGEngine()
        chunk_count = rag_engine.process_document(file_path, pk)

        from .models import Document
        document = Document.objects.get(id=document_id)
        document.chunk_count = chunk_count
        document.save()

        # 处理完后关闭连接，避免泄漏
        connections.close_all()
        logger.info(f'✅ 文档向量化完成 (doc_id={document_id}, chunks={chunk_count})')
    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(f'❌ 文档向量化失败 (doc_id={document_id}): {error_msg}')
        import traceback
        logger.error(traceback.format_exc())


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """知识库视图集"""
    serializer_class = KnowledgeBaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return KnowledgeBase.objects.all().order_by('-created_at')
        return KnowledgeBase.objects.filter(created_by=user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """上传文档到知识库"""
        knowledge_base = self.get_object()

        if 'file' not in request.FILES:
            return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES['file']
        file_ext = Path(file.name).suffix.lower()

        # 验证文件类型
        if file_ext not in ['.pdf', '.docx', '.txt']:
            return Response(
                {'error': '不支持的文件类型，仅支持 PDF、DOCX、TXT'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 创建上传目录
        upload_dir = Path(__file__).resolve().parent.parent / 'uploads' / f'kb_{pk}'
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = upload_dir / file.name
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        document = None
        try:
            # 创建文档记录
            document = Document.objects.create(
                knowledge_base=knowledge_base,
                title=file.name,
                file_path=str(file_path),
                file_type=file_ext[1:],  # 去掉点号
                file_size=file.size,
                uploaded_by=request.user
            )

            # 异步处理文档向量化（避免前端长时间等待）
            thread = threading.Thread(
                target=_process_document_async,
                args=(str(file_path), pk, document.id),
                daemon=True
            )
            thread.start()

            return Response({
                'message': '文档上传成功，正在后台处理中',
                'document_id': document.id,
                'chunk_count': 0
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            # 失败时清理文件和数据库记录
            if file_path.exists():
                file_path.unlink()
            if document:
                document.delete()
            return Response(
                {'error': f'文档上传失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_document(self, request, pk=None):
        """删除知识库中的文档"""
        knowledge_base = self.get_object()
        document_id = request.data.get('document_id')

        if not document_id:
            return Response({'error': '未提供文档ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            document = Document.objects.get(id=document_id, knowledge_base=knowledge_base)

            # 删除文件
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()

            # 删除数据库记录
            document.delete()

            return Response({'message': '文档删除成功'}, status=status.HTTP_200_OK)

        except Document.DoesNotExist:
            return Response({'error': '文档不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f'删除失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def ask(self, request, pk=None):
        """向知识库提问"""
        knowledge_base = self.get_object()
        question = request.data.get('question', '')
        session_id = request.data.get('session_id', '')
        mode = request.data.get('mode', 'knowledge')  # 获取模式参数，默认为知识库问答
        system_prompt = request.data.get('system_prompt', '')  # 获取 Skill 的系统提示词
        skill_name = request.data.get('skill_name', '')  # 获取 Skill 名称
        images = request.data.get('images', [])  # 获取图片列表（base64数组）

        print(f"DEBUG: 接收到的 session_id = '{session_id}', mode = '{mode}', skill = '{skill_name}', images_count = {len(images)}")

        if not question or not question.strip():
            return Response({'error': '问题不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rag_engine = RAGEngine()

            # 根据模式选择不同的回答方式
            if mode == 'chat':
                # 日常对话模式 - 直接调用LLM，不使用RAG
                result = rag_engine.chat(question, system_prompt=system_prompt, images=images)
            else:
                # 知识库问答模式 - 使用RAG检索增强（已支持图片）
                result = rag_engine.answer_question(
                    question, pk, system_prompt=system_prompt, images=images
                )

            # 如果没有session_id，生成一个新的
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())[:12]
                print(f"DEBUG: 生成新的 session_id = {session_id}")
            else:
                print(f"DEBUG: 使用现有的 session_id = {session_id}")

            # 保存对话消息
            chat_message = ChatMessage.objects.create(
                knowledge_base=knowledge_base,
                session_id=session_id,
                mode=mode,  # 保存模式
                question=question,
                answer=result['answer'],
                context_docs=result.get('context_docs', []),
                created_by=request.user
            )

            return Response({
                'answer': result['answer'],
                'context_docs': result.get('context_docs', []),
                'message_id': chat_message.id,
                'session_id': session_id,
                'skill_name': skill_name,  # 返回使用的 Skill 名称
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'问答失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def chat_history(self, request, pk=None):
        """获取知识库的对话历史"""
        knowledge_base = self.get_object()
        messages = ChatMessage.objects.filter(
            knowledge_base=knowledge_base,
            created_by=request.user
        ).order_by('-created_at')[:50]

        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def session_messages(self, request, pk=None):
        """获取指定会话的所有消息"""
        knowledge_base = self.get_object()
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response({'error': '缺少session_id参数'}, status=status.HTTP_400_BAD_REQUEST)

        messages = ChatMessage.objects.filter(
            knowledge_base=knowledge_base,
            session_id=session_id,
            created_by=request.user
        ).order_by('created_at')

        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def session_list(self, request, pk=None):
        """获取所有会话列表"""
        knowledge_base = self.get_object()
        from django.db.models import Max, Count
        
        sessions = ChatMessage.objects.filter(
            knowledge_base=knowledge_base,
            created_by=request.user
        ).values('session_id', 'mode').annotate(
            last_message_time=Max('created_at'),
            message_count=Count('id')
        ).order_by('-last_message_time')

        # 获取每个会话的第一条消息作为标题
        result = []
        for session in sessions:
            if session['session_id']:
                first_msg = ChatMessage.objects.filter(
                    knowledge_base=knowledge_base,
                    session_id=session['session_id'],
                    created_by=request.user
                ).order_by('created_at').first()  # 明确按创建时间正序排序
                
                result.append({
                    'session_id': session['session_id'],
                    'title': first_msg.question[:30] if first_msg else '新对话',
                    'last_message_time': session['last_message_time'],
                    'message_count': session['message_count'],
                    'mode': session['mode'] or 'knowledge'  # 添加模式字段
                })

        return Response(result)

    @action(detail=True, methods=['delete'])
    def delete_message(self, request, pk=None):
        """删除单条对话历史消息"""
        knowledge_base = self.get_object()
        message_id = request.data.get('message_id')

        if not message_id:
            return Response({'error': '未提供消息ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = ChatMessage.objects.get(
                id=message_id,
                knowledge_base=knowledge_base,
                created_by=request.user
            )
            message.delete()

            return Response({
                'success': True,
                'message': '消息删除成功'
            }, status=status.HTTP_200_OK)

        except ChatMessage.DoesNotExist:
            return Response({'error': '消息不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f'删除失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def batch_delete_messages(self, request, pk=None):
        """批量删除对话历史消息"""
        knowledge_base = self.get_object()
        message_ids = request.data.get('message_ids', [])

        if not message_ids or not isinstance(message_ids, list):
            return Response({'error': '未提供消息ID列表'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 删除属于当前用户和知识库的消息
            deleted_count = ChatMessage.objects.filter(
                id__in=message_ids,
                knowledge_base=knowledge_base,
                created_by=request.user
            ).delete()[0]

            return Response({
                'success': True,
                'deleted_count': deleted_count,
                'message': f'成功删除 {deleted_count} 条消息'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'批量删除失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_session(self, request, pk=None):
        """删除整个会话（所有消息）"""
        knowledge_base = self.get_object()
        session_id = request.data.get('session_id')

        if not session_id:
            return Response({'error': '未提供会话ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 删除属于当前用户、知识库和会话的所有消息
            deleted_count = ChatMessage.objects.filter(
                session_id=session_id,
                knowledge_base=knowledge_base,
                created_by=request.user
            ).delete()[0]

            return Response({
                'success': True,
                'deleted_count': deleted_count,
                'message': f'成功删除会话，共 {deleted_count} 条消息'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'删除会话失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def search(self, request, pk=None):
        """
        向量检索（纯检索，不经过 LLM 问答）

        前端搜索框 / Agent 知识检索工具 直接调用此接口。

        Query params:
            q (str): 搜索关键词/问题
            top_k (int): 返回结果数，默认 10
            threshold (float): 相似度阈值，默认 0.3
        """
        knowledge_base = self.get_object()
        query = request.query_params.get('q', '')
        top_k = int(request.query_params.get('top_k', 10))
        threshold = float(request.query_params.get('threshold', 0.3))

        if not query or not query.strip():
            return Response({'error': '搜索关键词不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rag_engine = RAGEngine()
            if not rag_engine.milvus_available:
                return Response({
                    'results': [],
                    'total': 0,
                    'message': 'Milvus 向量数据库未连接，无法搜索',
                })

            results = rag_engine.raw_vector_search(
                query=query,
                knowledge_base_id=knowledge_base.id,
                top_k=top_k,
                similarity_threshold=threshold,
            )

            return Response({
                'results': results,
                'total': len(results),
                'query': query,
                'kb_name': knowledge_base.name,
            })

        except Exception as e:
            logger.exception(f"[search] 向量检索失败: {e}")
            return Response(
                {'error': f'检索失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        获取知识库的向量统计信息

        Returns:
            {milvus_available, total_vectors, collection_name, kb_id, ...}
        """
        knowledge_base = self.get_object()
        try:
            rag_engine = RAGEngine()
            stats = rag_engine.get_kb_stats(knowledge_base.id)

            # 补充业务层统计
            stats.update({
                'kb_name': knowledge_base.name,
                'doc_count': knowledge_base.documents.count(),
                'total_messages': ChatMessage.objects.filter(
                    knowledge_base=knowledge_base
                ).count(),
            })

            return Response(stats)

        except Exception as e:
            logger.exception(f"[stats] 获取统计失败: {e}")
            return Response({
                'milvus_available': False,
                'kb_name': knowledge_base.name,
                'error': str(e),
            })

    def destroy(self, request, *args, **kwargs):
        """删除知识库及其所有数据"""
        instance = self.get_object()

        try:
            # 删除向量数据
            rag_engine = RAGEngine()
            rag_engine.delete_knowledge_base_data(instance.id)

            # 删除关联文档文件
            for doc in instance.documents.all():
                file_path = Path(doc.file_path)
                if file_path.exists():
                    file_path.unlink()

            # 删除数据库记录（级联删除）
            instance.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response(
                {'error': f'删除失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentViewSet(viewsets.ModelViewSet):
    """文档视图集（支持查看和删除）"""
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            queryset = Document.objects.all().order_by('-uploaded_at')
        else:
            queryset = Document.objects.filter(
                knowledge_base__created_by=user
            ).order_by('-uploaded_at')
        
        # 支持按知识库过滤
        kb_id = self.request.query_params.get('knowledge_base')
        if kb_id:
            queryset = queryset.filter(knowledge_base_id=kb_id)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载文档文件"""
        from django.http import FileResponse
        import os
        
        document = self.get_object()
        file_path = document.file_path
        
        if not os.path.exists(file_path):
            return Response({'error': '文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        
        # 获取文件名
        filename = os.path.basename(file_path)
        
        # 返回文件响应
        response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
        return response
    
    def destroy(self, request, *args, **kwargs):
        """删除文档及其关联的向量数据"""
        instance = self.get_object()
        
        # 删除文件
        import os
        if os.path.exists(instance.file_path):
            try:
                os.remove(instance.file_path)
            except Exception as e:
                logger.warning(f"删除文件失败: {e}")
        
        # 删除 Milvus 向量数据
        try:
            rag_engine = RAGEngine()
            if rag_engine.milvus_available:
                rag_engine.delete_document_vectors(instance.id)
                logger.info(f"[DocumentViewSet] 已删除文档 #{instance.id} 的向量数据")
        except Exception as e:
            logger.warning(f"[DocumentViewSet] 删除向量数据失败（不影响主流程）: {e}")
        
        return super().destroy(request, *args, **kwargs)


# ============================================================
# 独立视图函数：绕过 DRF @action 的 StreamingHttpResponse 限制
# ============================================================
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated

@csrf_exempt
def ask_stream_view(request, pk):
    """原生 Django 视图处理 SSE 流式问答"""
    import json
    import uuid
    import traceback
    import logging

    logger = logging.getLogger('django')
    logger.info(f"[ask_stream_view] 收到请求 pk={pk}, method={request.method}")

    try:
        # 手动 JWT 认证
        try:
            auth = JWTAuthentication()
            auth_result = auth.authenticate(request)
            if auth_result is None:
                return JsonResponse(
                    {'detail': '身份认证信息未提供。'},
                    status=401
                )
            user, _ = auth_result
        except (AuthenticationFailed, NotAuthenticated) as e:
            return JsonResponse(
                {'detail': str(e)},
                status=401
            )

        # 验证知识库存在，管理员可访问所有知识库
        try:
            if user.is_admin:
                knowledge_base = KnowledgeBase.objects.get(id=pk)
            else:
                knowledge_base = KnowledgeBase.objects.get(id=pk, created_by=user)
        except KnowledgeBase.DoesNotExist:
            return JsonResponse(
                {'detail': '知识库不存在或无权访问。'},
                status=404
            )

        # 解析请求体
        try:
            body = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': '请求体不是有效的 JSON'},
                status=400
            )

        question = body.get('question', '')
        session_id = body.get('session_id', '')
        mode = body.get('mode', 'knowledge')
        system_prompt = body.get('system_prompt', '')
        skill_name = body.get('skill_name', '')
        images = body.get('images', [])
        enable_reasoning = body.get('enable_reasoning', False)

        if not question or not question.strip():
            return JsonResponse(
                {'error': '问题不能为空'},
                status=400
            )

        # 生成或使用 session_id
        if not session_id:
            session_id = str(uuid.uuid4())[:12]

        # 在生成器外部初始化 RAGEngine，提前发现问题
        try:
            rag_engine = RAGEngine()
            logger.info("[ask_stream_view] RAGEngine 初始化成功")
        except Exception as e:
            logger.error(f"RAGEngine 初始化失败: {traceback.format_exc()}")
            return JsonResponse(
                {'error': f'AI引擎初始化失败: {str(e)}'},
                status=500
            )

        # 提取必要数据，避免闭包中引用 ORM 对象（防止数据库连接关闭问题）
        kb_id = knowledge_base.id
        user_id = user.id
        import time
        start_time = time.time()  # 记录开始时间

        def generate():
            full_answer = ''
            context_docs = []
            logger.info("[generate] 生成器开始执行")

            # 先保存用户问题（确保即使中途停止也有历史记录）
            from django.contrib.auth import get_user_model
            User = get_user_model()
            kb_obj = KnowledgeBase.objects.get(id=kb_id)
            user_obj = User.objects.get(id=user_id)
            chat_msg = ChatMessage.objects.create(
                knowledge_base=kb_obj,
                session_id=session_id,
                mode=mode,
                question=question,
                answer='',  # 初始为空，流式完成后更新
                context_docs=context_docs,
                response_time=0,
                created_by=user_obj
            )
            logger.info(f"[generate] ChatMessage 初始记录已创建，id={chat_msg.id}")

            try:
                # 先发送 session_id 和 metadata
                meta_data = json.dumps({
                    'type': 'meta',
                    'session_id': session_id,
                    'skill_name': skill_name,
                }, ensure_ascii=False)
                yield f"data: {meta_data}\n\n"
                logger.info(f"[generate] meta 已发送, mode={mode}")

                # 根据模式选择生成器
                if mode == 'chat':
                    logger.info("[generate] 调用 chat_stream...")
                    token_generator = rag_engine.chat_stream(
                        question, system_prompt=system_prompt, images=images,
                        enable_reasoning=enable_reasoning
                    )
                else:
                    logger.info("[generate] 调用 answer_question_stream...")
                    token_generator = rag_engine.answer_question_stream(
                        question, int(pk), system_prompt=system_prompt,
                        enable_reasoning=enable_reasoning, images=images
                    )

                logger.info("[generate] 开始迭代 token_generator...")
                for item in token_generator:
                    # 支持两种格式：dict {'type': '...', 'content': '...'} 或纯字符串（兼容旧代码）
                    if isinstance(item, dict):
                        ev_type = item.get('type', 'token')
                        ev_content = item.get('content', '')
                    else:
                        ev_type = 'token'
                        ev_content = str(item)

                    if ev_type == 'token':
                        full_answer += ev_content

                    ev_data = json.dumps({
                        'type': ev_type,
                        'content': ev_content,
                    }, ensure_ascii=False)
                    try:
                        yield f"data: {ev_data}\n\n"
                    except GeneratorExit:
                        logger.info("[generate] 客户端已断开（GeneratorExit），保存已生成的回答")
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        chat_msg.answer = full_answer
                        chat_msg.response_time = elapsed_ms
                        chat_msg.save()
                        logger.info(f"[generate] 已保存部分回答，{len(full_answer)} 字符，耗时 {elapsed_ms}ms")
                        return

                # 计算耗时
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[generate] token 迭代完成，耗时 {elapsed_ms}ms，发送 done")

                done_data = json.dumps({
                    'type': 'done',
                    'full_answer': full_answer,
                    'context_docs': context_docs,
                    'response_time': elapsed_ms,  # 前端可显示
                }, ensure_ascii=False)
                yield f"data: {done_data}\n\n"

                # 更新消息为完整回答
                logger.info("[generate] 更新 ChatMessage 完整回答...")
                chat_msg.answer = full_answer
                chat_msg.response_time = elapsed_ms
                chat_msg.save()
                logger.info("[generate] ChatMessage 更新完成")

            except Exception as e:
                logger.error(f"[generate] ask_stream 异常: {traceback.format_exc()}")
                # 即使出错也保存已生成的部分回答
                if full_answer:
                    chat_msg.answer = full_answer
                    chat_msg.save()
                    logger.info("[generate] 异常时保存了部分回答")
                error_data = json.dumps({
                    'type': 'error',
                    'message': f'回答失败: {str(e)}',
                }, ensure_ascii=False)
                yield f"data: {error_data}\n\n"

        # 使用完整的 generate() 函数，但加上详细的日志
        logger.info("[ask_stream_view] 准备创建 StreamingHttpResponse")
        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream',
            status=200,
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        logger.info("[ask_stream_view] StreamingHttpResponse 已创建，准备返回")
        return response

    except Exception as e:
        logger.error(f"[ask_stream_view] 未捕获异常: {traceback.format_exc()}")
        return JsonResponse(
            {'error': f'服务器内部错误: {str(e)}'},
            status=500
        )




