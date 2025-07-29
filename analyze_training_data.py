#!/usr/bin/env python3
"""
Скрипт для аналізу тренувальних даних OCR
Використовується для покращення точності розпізнавання
"""

import os
import json
from training_data_collector import TrainingDataCollector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Основний функціонал аналізу"""
    collector = TrainingDataCollector()
    
    print("🔍 АНАЛІЗ ТРЕНУВАЛЬНИХ ДАНИХ OCR")
    print("=" * 50)
    
    # Генеруємо звіт
    report_file = collector.generate_training_report()
    
    if os.path.exists(report_file):
        print(f"📊 Звіт згенеровано: {report_file}")
        
        # Показуємо зміст звіту
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print("\n" + content)
    else:
        print("❌ Звіт не згенеровано")
    
    # Показуємо структуру тренувальних даних
    print("\n📁 СТРУКТУРА ТРЕНУВАЛЬНИХ ДАНИХ:")
    print("-" * 30)
    
    training_dir = collector.training_dir
    if os.path.exists(training_dir):
        invoices = [item for item in os.listdir(training_dir) 
                   if os.path.isdir(os.path.join(training_dir, item)) 
                   and item.startswith("invoice_")]
        
        print(f"Знайдено накладних: {len(invoices)}")
        
        for invoice in invoices[:10]:  # Показуємо перші 10
            invoice_path = os.path.join(training_dir, invoice)
            annotation_file = os.path.join(invoice_path, "manual_annotation.json")
            
            if os.path.exists(annotation_file):
                try:
                    with open(annotation_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        bakery_name = data.get('bakery_name', {}).get('correct_name', 'Не анотовано')
                        products_count = len(data.get('products', []))
                        print(f"  • {invoice}: {bakery_name} ({products_count} продуктів)")
                except:
                    print(f"  • {invoice}: Помилка читання анотації")
            else:
                print(f"  • {invoice}: Очікує анотації")
        
        if len(invoices) > 10:
            print(f"  ... та ще {len(invoices) - 10} накладних")
    else:
        print("Папка тренувальних даних не знайдена")
    
    # Показуємо рекомендації
    print("\n💡 РЕКОМЕНДАЦІЇ:")
    print("-" * 20)
    print("1. Надішліть боту кілька накладних для збору даних")
    print("2. Відредагуйте файли manual_annotation.json в папці training_data")
    print("3. Запустіть цей скрипт знову для аналізу результатів")
    print("4. На основі аналізу покращіть алгоритм OCR")

if __name__ == "__main__":
    main() 