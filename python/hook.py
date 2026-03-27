#!/usr/bin/env python3
"""
OpenClaw Neo4j Auto-Record Hook v2
自动记录所有对话到 Neo4j（支持项目维度关联）

集成方式：在 OpenClaw 消息处理流程中调用

作者：知微
日期：2026-03-27
"""

import sys
import os
from typing import Optional
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neo4j_graph_memory import get_graph_memory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 Graph Memory
try:
    graph_memory = get_graph_memory()
    logger.info("✅ Neo4j Graph Memory V2 initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize: {e}")
    graph_memory = None


def record_conversation(user_id: str, message: str, response: str, 
                       agent_id: Optional[str] = None) -> bool:
    """
    记录对话到 Neo4j（增强版 - 自动识别项目和模块）
    
    Args:
        user_id: 用户 ID
        message: 用户消息
        response: AI 回复
        agent_id: 指定智能体 ID（可选，不指定则自动识别）
    
    Returns:
        bool: 是否成功记录
    """
    if not graph_memory:
        logger.error("Graph Memory not initialized")
        return False
    
    try:
        result = graph_memory.insert_after_chat(
            user_id=user_id,
            intent=message,
            task='对话记录',
            solution=response,
            result='success',
            intent_type='chat',
            confidence=1.0,
            agent_id=agent_id  # 传递智能体 ID
        )
        
        if result:
            logger.info(f"✅ Recorded: {user_id} - {message[:50]}...")
        else:
            logger.error(f"❌ Failed to record: {user_id}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Error recording: {e}")
        return False


def retrieve_context(user_id: str, keyword: str = "", limit: int = 5) -> list:
    """
    检索用户历史对话上下文
    
    Args:
        user_id: 用户 ID
        keyword: 关键词（可选）
        limit: 返回数量
    
    Returns:
        list: 历史记录列表
    """
    if not graph_memory:
        return []
    
    try:
        history = graph_memory.retrieve_before_chat(user_id, keyword, limit)
        return history
    
    except Exception as e:
        logger.error(f"❌ Error retrieving: {e}")
        return []


# 测试与 CLI 入口
if __name__ == '__main__':
    if len(sys.argv) >= 4:
        user_id = sys.argv[1]
        message = sys.argv[2]
        response = sys.argv[3]
        agent_id = sys.argv[4] if len(sys.argv) > 4 else None
        
        result = record_conversation(user_id, message, response, agent_id)
        if result:
            print("SUCCESS")
            sys.exit(0)
        else:
            print("FAILED")
            sys.exit(1)
    else:
        print("🧪 Testing OpenClaw Neo4j Hook...")
        
        # 测试记录
        result = record_conversation(
            user_id='Boss',
            message='测试自动记录功能',
            response='这是测试回复'
        )
        print(f"Record result: {result}")
        
        # 测试检索
        context = retrieve_context('Boss', '测试', 5)
        print(f"Retrieved {len(context)} records")
        for record in context:
            print(f"  - {record.get('content', 'N/A')}")
        
        print("\n✅ Hook test completed!")
