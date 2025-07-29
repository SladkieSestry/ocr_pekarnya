import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class TrainingDataCollector:
    def __init__(self):
        """Ініціалізація збирача тренувальних даних"""
        self.training_dir = "training_data"
        self.raw_data_dir = os.path.join(self.training_dir, "raw_ocr")
        self.processed_data_dir = os.path.join(self.training_dir, "processed")
        self.annotations_dir = os.path.join(self.training_dir, "annotations")
        
        # Створюємо структуру папок
        for directory in [self.training_dir, self.raw_data_dir, self.processed_data_dir, self.annotations_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Створено папку: {directory}")
    
    def save_invoice_data(self, invoice_id: str, photo1_path: str, photo2_path: str, 
                         raw_text1: List[str], raw_text2: List[str], 
                         ocr_results: Dict[str, Any]) -> str:
        """Збереження даних накладної для тренування"""
        try:
            # Створюємо папку для цієї накладної
            invoice_dir = os.path.join(self.training_dir, f"invoice_{invoice_id}")
            if not os.path.exists(invoice_dir):
                os.makedirs(invoice_dir)
            
            # Копіюємо фото
            photo1_dest = os.path.join(invoice_dir, "photo1.jpg")
            photo2_dest = os.path.join(invoice_dir, "photo2.jpg")
            shutil.copy2(photo1_path, photo1_dest)
            shutil.copy2(photo2_path, photo2_dest)
            
            # Зберігаємо сирий текст OCR
            raw_text_file = os.path.join(invoice_dir, "raw_ocr_text.txt")
            with open(raw_text_file, 'w', encoding='utf-8') as f:
                f.write("=== ФОТО 1 ===\n")
                for i, text in enumerate(raw_text1, 1):
                    f.write(f"{i:3d}. {text}\n")
                f.write("\n=== ФОТО 2 ===\n")
                for i, text in enumerate(raw_text2, 1):
                    f.write(f"{i:3d}. {text}\n")
            
            # Зберігаємо результати OCR
            ocr_results_file = os.path.join(invoice_dir, "ocr_results.json")
            with open(ocr_results_file, 'w', encoding='utf-8') as f:
                json.dump(ocr_results, f, ensure_ascii=False, indent=2)
            
            # Створюємо файл для ручної анотації
            annotation_file = os.path.join(invoice_dir, "manual_annotation.json")
            self.create_annotation_template(annotation_file, ocr_results)
            
            logger.info(f"Збережено дані накладної {invoice_id} в {invoice_dir}")
            return invoice_dir
            
        except Exception as e:
            logger.error(f"Помилка збереження даних накладної: {e}")
            return None
    
    def create_annotation_template(self, annotation_file: str, ocr_results: Dict[str, Any]):
        """Створення шаблону для ручної анотації"""
        template = {
            "invoice_id": "",
            "date_annotated": datetime.now().isoformat(),
            "bakery_name": {
                "correct_name": "",
                "found_in_ocr": ocr_results.get('bakery_name', ''),
                "confidence": 0.0,
                "notes": ""
            },
            "products": [],
            "total_quantity": 0.0,
            "total_amount": 0.0,
            "ocr_quality": {
                "overall_quality": 0.0,  # 0-10
                "text_clearness": 0.0,   # 0-10
                "layout_quality": 0.0,   # 0-10
                "notes": ""
            },
            "manual_corrections": {
                "missing_products": [],
                "incorrect_quantities": [],
                "incorrect_prices": [],
                "other_issues": []
            }
        }
        
        # Додаємо знайдені продукти для анотації
        for product in ocr_results.get('products', []):
            template["products"].append({
                "ocr_name": product.get('name', ''),
                "ocr_quantity": product.get('quantity', 0),
                "ocr_price": product.get('price', 0),
                "ocr_total": product.get('total', 0),
                "correct_name": "",
                "correct_quantity": 0.0,
                "correct_price": 0.0,
                "correct_total": 0.0,
                "is_correct": False,
                "notes": ""
            })
        
        with open(annotation_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
    
    def load_annotated_data(self) -> List[Dict[str, Any]]:
        """Завантаження анотованих даних"""
        annotated_data = []
        
        for item in os.listdir(self.training_dir):
            item_path = os.path.join(self.training_dir, item)
            if os.path.isdir(item_path) and item.startswith("invoice_"):
                annotation_file = os.path.join(item_path, "manual_annotation.json")
                if os.path.exists(annotation_file):
                    try:
                        with open(annotation_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            annotated_data.append(data)
                    except Exception as e:
                        logger.error(f"Помилка завантаження анотації {annotation_file}: {e}")
        
        return annotated_data
    
    def analyze_ocr_performance(self) -> Dict[str, Any]:
        """Аналіз продуктивності OCR на основі анотованих даних"""
        annotated_data = self.load_annotated_data()
        
        if not annotated_data:
            return {"message": "Немає анотованих даних для аналізу"}
        
        analysis = {
            "total_invoices": len(annotated_data),
            "bakery_name_accuracy": 0.0,
            "product_detection_rate": 0.0,
            "quantity_accuracy": 0.0,
            "price_accuracy": 0.0,
            "average_ocr_quality": 0.0,
            "common_issues": [],
            "recommendations": []
        }
        
        total_products = 0
        correct_products = 0
        correct_quantities = 0
        correct_prices = 0
        correct_bakery_names = 0
        total_quality = 0.0
        
        for invoice in annotated_data:
            # Аналіз назви пекарні
            if invoice.get('bakery_name', {}).get('is_correct', False):
                correct_bakery_names += 1
            
            # Аналіз продуктів
            for product in invoice.get('products', []):
                total_products += 1
                if product.get('is_correct', False):
                    correct_products += 1
                
                # Аналіз кількості
                if abs(product.get('ocr_quantity', 0) - product.get('correct_quantity', 0)) < 0.1:
                    correct_quantities += 1
                
                # Аналіз ціни
                if abs(product.get('ocr_price', 0) - product.get('correct_price', 0)) < 0.01:
                    correct_prices += 1
            
            # Аналіз якості OCR
            quality = invoice.get('ocr_quality', {})
            total_quality += quality.get('overall_quality', 0)
        
        # Розрахунок відсотків
        if len(annotated_data) > 0:
            analysis['bakery_name_accuracy'] = (correct_bakery_names / len(annotated_data)) * 100
        
        if total_products > 0:
            analysis['product_detection_rate'] = (correct_products / total_products) * 100
            analysis['quantity_accuracy'] = (correct_quantities / total_products) * 100
            analysis['price_accuracy'] = (correct_prices / total_products) * 100
        
        if len(annotated_data) > 0:
            analysis['average_ocr_quality'] = total_quality / len(annotated_data)
        
        return analysis
    
    def generate_training_report(self) -> str:
        """Генерація звіту про тренувальні дані"""
        analysis = self.analyze_ocr_performance()
        
        report_file = os.path.join(self.training_dir, "training_report.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("ЗВІТ ПРО ТРЕНУВАЛЬНІ ДАНІ OCR\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Загальна кількість накладних: {analysis.get('total_invoices', 0)}\n")
            f.write(f"Точність розпізнавання назв пекарень: {analysis.get('bakery_name_accuracy', 0):.1f}%\n")
            f.write(f"Точність розпізнавання продуктів: {analysis.get('product_detection_rate', 0):.1f}%\n")
            f.write(f"Точність розпізнавання кількості: {analysis.get('quantity_accuracy', 0):.1f}%\n")
            f.write(f"Точність розпізнавання цін: {analysis.get('price_accuracy', 0):.1f}%\n")
            f.write(f"Середня якість OCR: {analysis.get('average_ocr_quality', 0):.1f}/10\n\n")
            
            f.write("РЕКОМЕНДАЦІЇ ДЛЯ ПОКРАЩЕННЯ:\n")
            f.write("-" * 30 + "\n")
            
            if analysis.get('bakery_name_accuracy', 0) < 70:
                f.write("• Покращити алгоритм розпізнавання назв пекарень\n")
            
            if analysis.get('product_detection_rate', 0) < 80:
                f.write("• Додати більше патернів для розпізнавання продуктів\n")
            
            if analysis.get('quantity_accuracy', 0) < 90:
                f.write("• Покращити розпізнавання чисел та кількості\n")
            
            if analysis.get('average_ocr_quality', 0) < 7:
                f.write("• Покращити якість фото або попередню обробку зображень\n")
        
        return report_file 