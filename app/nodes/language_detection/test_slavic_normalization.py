# Тестовые примеры для проверки нормализации славянских языков
# 
# Эти фразы будут определяться langdetect как разные языки,
# но должны нормализоваться к "ru" для унифицированного RAG поиска

test_cases = {
    "bulgarian": {
        "phrase": "Отлично, а крипту?",  # Короткая фраза - langdetect может определить как BG
        "expected_detected": "bg",
        "expected_normalized": "ru"
    },
    "ukrainian": {
        "phrase": "Як оплатити картою?",  # Украинский
        "expected_detected": "uk",
        "expected_normalized": "ru"
    },
    "belarusian": {
        "phrase": "Як працуе гэта?",  # Белорусский
        "expected_detected": "be", 
        "expected_normalized": "ru"
    },
    "russian": {
        "phrase": "Как это работает?",  # Чистый русский
        "expected_detected": "ru",
        "expected_normalized": "ru"
    }
}

# Использование:
# from app.nodes.language_detection.node import LanguageDetectionNode
# 
# node = LanguageDetectionNode()
# 
# for lang, test in test_cases.items():
#     result = await node.execute({"question": test["phrase"]})
#     print(f"{lang}: {result['detected_language']} (conf: {result['language_confidence']})")
#     assert result['detected_language'] == test['expected_normalized']
