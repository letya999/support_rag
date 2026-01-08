"""
Тест для проверки исправленного детектора петель.
Проверяет, что детектор НЕ срабатывает на разные темы.
"""
import asyncio
from app.nodes.dialog_analysis.loop_detector import detect_topic_loop


async def test_no_false_positive():
    """Тест: разные темы НЕ должны определяться как петля"""
    
    # История из трейса - три РАЗНЫЕ темы
    conversation_history = [
        {"role": "user", "content": "Чем я могу оплатить заказ?"},
        {"role": "assistant", "content": "Не смог найти ответ."},
        {"role": "user", "content": "Какие способы доставки есть в сервисе?"},
        {"role": "assistant", "content": "К сожалению, у меня нет информации..."},
        {"role": "user", "content": "Не смог найти ответ."},
    ]
    
    current_question = "Как мне защитить аккаунт от взлома?"
    
    result = await detect_topic_loop(
        current_question=current_question,
        conversation_history=conversation_history,
        similarity_threshold=0.8,
        window_size=4,
        min_messages_for_loop=3
    )
    
    print("=" * 60)
    print("ТЕСТ: Разные темы (НЕ должно быть петли)")
    print("=" * 60)
    print(f"Текущий вопрос: {current_question}")
    print(f"\nИстория:")
    for msg in conversation_history:
        if msg["role"] == "user":
            print(f"  - {msg['content']}")
    
    print(f"\nРезультат:")
    print(f"  topic_loop_detected: {result['topic_loop_detected']}")
    print(f"  loop_confidence: {result['loop_confidence']:.3f}")
    print(f"  similar_messages_count: {result['similar_messages_count']}")
    print(f"  average_similarity: {result['average_similarity']:.3f}")
    
    if result['topic_loop_detected']:
        print("\n❌ ОШИБКА: Детектор ложно определил петлю на разных темах!")
        return False
    else:
        print("\n✅ УСПЕХ: Детектор правильно НЕ определил петлю")
        return True


async def test_real_loop():
    """Тест: повторение ОДНОЙ темы должно определяться как петля"""
    
    conversation_history = [
        {"role": "user", "content": "Как сбросить пароль?"},
        {"role": "assistant", "content": "Перейдите в настройки..."},
        {"role": "user", "content": "Не могу восстановить пароль"},
        {"role": "assistant", "content": "Попробуйте через email..."},
    ]
    
    current_question = "Как мне сбросить свой пароль?"
    
    result = await detect_topic_loop(
        current_question=current_question,
        conversation_history=conversation_history,
        similarity_threshold=0.8,
        window_size=4,
        min_messages_for_loop=3
    )
    
    print("\n" + "=" * 60)
    print("ТЕСТ: Повторение одной темы (ДОЛЖНА быть петля)")
    print("=" * 60)
    print(f"Текущий вопрос: {current_question}")
    print(f"\nИстория:")
    for msg in conversation_history:
        if msg["role"] == "user":
            print(f"  - {msg['content']}")
    
    print(f"\nРезультат:")
    print(f"  topic_loop_detected: {result['topic_loop_detected']}")
    print(f"  loop_confidence: {result['loop_confidence']:.3f}")
    print(f"  similar_messages_count: {result['similar_messages_count']}")
    print(f"  average_similarity: {result['average_similarity']:.3f}")
    
    if result['topic_loop_detected']:
        print("\n✅ УСПЕХ: Детектор правильно определил петлю")
        return True
    else:
        print("\n⚠️ ВНИМАНИЕ: Детектор НЕ определил реальную петлю")
        return False


async def main():
    print("\n🔍 Тестирование исправленного детектора петель\n")
    
    test1 = await test_no_false_positive()
    test2 = await test_real_loop()
    
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    print("=" * 60)
    print(f"Тест 1 (разные темы): {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Тест 2 (реальная петля): {'✅ PASSED' if test2 else '⚠️ NEEDS REVIEW'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
