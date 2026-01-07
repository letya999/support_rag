"""
Test script for Topic Loop Detection

Tests the loop detector with sample conversations.
"""
import asyncio
from app.nodes.dialog_analysis.loop_detector import detect_topic_loop


async def test_loop_detection():
    print("=" * 60)
    print("TOPIC LOOP DETECTION TESTS")
    print("=" * 60)
    
    # Test 1: Clear loop - same question repeated
    print("\n📝 Test 1: Clear Loop (Same Question)")
    print("-" * 60)
    
    history1 = [
        {"role": "user", "content": "Как сбросить пароль?"},
        {"role": "assistant", "content": "Вот инструкция..."},
        {"role": "user", "content": "Как мне сбросить пароль?"},
        {"role": "assistant", "content": "Используйте кнопку..."},
        {"role": "user", "content": "Скажите как сбросить пароль"},
    ]
    
    result1 = await detect_topic_loop(
        current_question="Объясните как сбросить пароль",
        conversation_history=history1,
        similarity_threshold=0.8,
        window_size=4,
        min_messages_for_loop=3
    )
    
    print(f"Result: {result1}")
    print(f"✅ Loop Detected: {result1['topic_loop_detected']}")
    print(f"   Confidence: {result1['loop_confidence']:.2f}")
    print(f"   Similar Messages: {result1['similar_messages_count']}")
    print(f"   Avg Similarity: {result1['average_similarity']:.2f}")
    
    # Test 2: No loop - different topics
    print("\n📝 Test 2: No Loop (Different Topics)")
    print("-" * 60)
    
    history2 = [
        {"role": "user", "content": "Как изменить email?"},
        {"role": "assistant", "content": "Зайдите в настройки..."},
        {"role": "user", "content": "Как удалить аккаунт?"},
        {"role": "assistant", "content": "Напишите в поддержку..."},
        {"role": "user", "content": "Как обновить телефон?"},
    ]
    
    result2 = await detect_topic_loop(
        current_question="Где найти статистику?",
        conversation_history=history2,
        similarity_threshold=0.8,
        window_size=4,
        min_messages_for_loop=3
    )
    
    print(f"Result: {result2}")
    print(f"❌ Loop Detected: {result2['topic_loop_detected']}")
    print(f"   Confidence: {result2['loop_confidence']:.2f}")
    print(f"   Similar Messages: {result2['similar_messages_count']}")
    print(f"   Avg Similarity: {result2['average_similarity']:.2f}")
    
    # Test 3: Edge case - only 2 messages
    print("\n📝 Test 3: Edge Case (Too Few Messages)")
    print("-" * 60)
    
    history3 = [
        {"role": "user", "content": "Привет"},
    ]
    
    result3 = await detect_topic_loop(
        current_question="Как сбросить пароль?",
        conversation_history=history3,
        similarity_threshold=0.8,
        window_size=4,
        min_messages_for_loop=3
    )
    
    print(f"Result: {result3}")
    print(f"❌ Loop Detected: {result3['topic_loop_detected']}")
    print(f"   (Not enough messages to detect loop)")
    
    # Test 4: Semantic similarity - same intent, different wording
    print("\n📝 Test 4: Semantic Similarity (Same Intent)")
    print("-" * 60)
    
    history4 = [
        {"role": "user", "content": "My account is locked"},
        {"role": "assistant", "content": "Try resetting..."},
        {"role": "user", "content": "I can't access my account"},
        {"role": "assistant", "content": "Check your email..."},
        {"role": "user", "content": "Account is still blocked"},
    ]
    
    result4 = await detect_topic_loop(
        current_question="Still cannot login to my account",
        conversation_history=history4,
        similarity_threshold=0.8,
        window_size=4,
        min_messages_for_loop=3
    )
    
    print(f"Result: {result4}")
    print(f"🔍 Loop Detected: {result4['topic_loop_detected']}")
    print(f"   Confidence: {result4['loop_confidence']:.2f}")
    print(f"   Similar Messages: {result4['similar_messages_count']}")
    print(f"   Avg Similarity: {result4['average_similarity']:.2f}")
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_loop_detection())
