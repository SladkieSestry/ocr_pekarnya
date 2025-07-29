import easyocr
import re
from typing import List, Dict, Tuple, Optional
import logging
import json

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        """Ініціалізація OCR з підтримкою української та російської мов"""
        self.reader = easyocr.Reader(['uk', 'ru', 'en'], gpu=False)
        logger.info("OCR процесор ініціалізовано")
        
        # Завантажуємо патерни з бланка
        self.load_blank_patterns()
    
    def load_blank_patterns(self):
        """Завантаження патернів з бланка"""
        try:
            with open('blank_patterns.json', 'r', encoding='utf-8') as f:
                self.blank_patterns = json.load(f)
            logger.info("Завантажено патерни з бланка")
        except:
            self.blank_patterns = {}
            logger.warning("Не вдалося завантажити патерни з бланка")
    
    def extract_text(self, image_path: str) -> List[Tuple]:
        """Розпізнавання тексту з зображення"""
        try:
            results = self.reader.readtext(image_path)
            logger.info(f"Розпізнано {len(results)} текстових блоків з {image_path}")
            return results
        except Exception as e:
            logger.error(f"Помилка OCR для {image_path}: {e}")
            return []
    
    def extract_bakery_name(self, ocr_results: List[Tuple]) -> Optional[str]:
        """Витяг назви пекарні з OCR результатів"""
        if not ocr_results:
            return None
        
        # Шукаємо назву пекарні в перших рядках
        for i, (bbox, text, confidence) in enumerate(ocr_results[:15]):
            text = text.strip().upper()
            
            # Патерни для назв пекарень
            bakery_patterns = [
                r'ПЕКАРНЯ\s+["\']?([^"\']+)["\']?',
                r'ТОВ\s+["\']?([^"\']+)["\']?',
                r'ПП\s+["\']?([^"\']+)["\']?',
                r'ФОП\s+["\']?([^"\']+)["\']?',
                r'["\']?([А-ЯІЇЄ\s]+(?:ПЕКАРНЯ|ХЛІБ|БУЛОЧНА|КОНДИТЕРСЬКА))["\']?',
                r'["\']?([А-ЯІЇЄ\s]{3,}(?:ПРОДАКШН|ПРОДАКШЕН|ПРОДАКШИН))["\']?',
                r'["\']?([А-ЯІЇЄ\s]{3,}(?:КОМПАНІЯ|КОМПАНИЯ))["\']?',
                r'["\']?([А-ЯІЇЄ\s]{3,}(?:ТОРГОВА|ТОРГОВО))["\']?',
            ]
            
            for pattern in bakery_patterns:
                match = re.search(pattern, text)
                if match:
                    bakery_name = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    bakery_name = re.sub(r'["\']', '', bakery_name).strip()
                    if len(bakery_name) > 3:  # Мінімальна довжина назви
                        logger.info(f"Знайдено назву пекарні: {bakery_name}")
                        return bakery_name
        
        # Якщо не знайдено за патернами, шукаємо рядки з високою впевненістю
        for bbox, text, confidence in ocr_results[:10]:
            text = text.strip()
            if confidence > 0.7 and len(text) > 5 and len(text) < 50:
                # Перевіряємо, чи не містить цифри або спецсимволи
                if not re.search(r'\d', text) and not re.search(r'[^\w\s]', text):
                    logger.info(f"Знайдено можливу назву пекарні: {text}")
                    return text
        
        return None
    
    def extract_products_data(self, ocr_results: List[Tuple]) -> List[Dict]:
        """Витяг даних про продукти з OCR результатів"""
        products = []
        
        for bbox, text, confidence in ocr_results:
            text = text.strip()
            
            # Пропускаємо рядки з низькою впевненістю
            if confidence < 0.4:
                continue
            
            # Шукаємо рядки з продуктами (кількість, назва, ціна)
            product_data = self.parse_product_line(text)
            if product_data:
                products.append(product_data)
        
        return products
    
    def parse_product_line(self, text: str) -> Optional[Dict]:
        """Парсинг рядка з продуктом з урахуванням формату бланка"""
        # Формат бланка: номер | назва продукту | код | ціна
        # Приклад: "1 | Багет ВП 230г з Ковб та Сир | 43056 | 36"
        
        # Патерни для рядків з продуктами
        patterns = [
            # Формат бланка: номер назва_продукту код ціна
            r'(\d+)\s*[|]\s*([А-ЯІЇЄ\w\s]+?)\s*[|]\s*(\d+)\s*[|]\s*(\d+(?:[.,]\d+)?)',
            # Формат бланка: номер назва_продукту код ціна (без |)
            r'(\d+)\s+([А-ЯІЇЄ\w\s]+?)\s+(\d+)\s+(\d+(?:[.,]\d+)?)',
            # Формат: кількість назва_продукту ціна
            r'(\d+(?:[.,]\d+)?)\s+([А-ЯІЇЄ\w\s]+?)\s+(\d+(?:[.,]\d+)?)',
            # Формат: назва_продукту кількість ціна
            r'([А-ЯІЇЄ\w\s]+?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)',
            # Формат: кількість x назва_продукту
            r'(\d+)\s*[xXхХ]\s*([А-ЯІЇЄ\w\s]+)',
            # Формат: кількість - назва_продукту
            r'(\d+(?:[.,]\d+)?)\s*[-–—]\s*([А-ЯІЇЄ\w\s]+)',
            # Формат: назва_продукту - кількість
            r'([А-ЯІЇЄ\w\s]+?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)',
            # Простий формат: кількість назва
            r'(\d+(?:[.,]\d+)?)\s+([А-ЯІЇЄ\w\s]{2,})',
            # Простий формат: назва кількість
            r'([А-ЯІЇЄ\w\s]{2,})\s+(\d+(?:[.,]\d+)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                
                # Визначаємо, що є що залежно від патерну
                if len(groups) == 4 and pattern.startswith(r'(\d+)\s*[|]'):
                    # Формат бланка: номер | назва | код | ціна
                    product_number = int(groups[0])
                    product_name = groups[1].strip()
                    product_code = groups[2]
                    price = float(groups[3].replace(',', '.'))
                    quantity = 1.0  # За замовчуванням 1
                elif len(groups) == 4 and pattern.startswith(r'(\d+)\s+'):
                    # Формат: номер назва код ціна
                    product_number = int(groups[0])
                    product_name = groups[1].strip()
                    product_code = groups[2]
                    price = float(groups[3].replace(',', '.'))
                    quantity = 1.0
                elif len(groups) == 3:
                    # Перевіряємо, чи перша група - число
                    if re.match(r'\d+(?:[.,]\d+)?', groups[0]):
                        quantity = float(groups[0].replace(',', '.'))
                        product_name = groups[1].strip()
                        price = float(groups[2].replace(',', '.'))
                    else:
                        product_name = groups[0].strip()
                        quantity = float(groups[1].replace(',', '.'))
                        price = float(groups[2].replace(',', '.'))
                elif len(groups) == 2:
                    # Перевіряємо, чи перша група - число
                    if re.match(r'\d+(?:[.,]\d+)?', groups[0]):
                        quantity = float(groups[0].replace(',', '.'))
                        product_name = groups[1].strip()
                        price = 0.0  # Ціна не вказана
                    else:
                        product_name = groups[0].strip()
                        quantity = float(groups[1].replace(',', '.'))
                        price = 0.0
                else:
                    continue
                
                # Валідація даних
                if self.is_valid_product(product_name, quantity):
                    return {
                        'name': product_name,
                        'quantity': quantity,
                        'price': price,
                        'total': quantity * price if price > 0 else 0,
                        'code': product_code if 'product_code' in locals() else None
                    }
        
        return None
    
    def is_valid_product(self, name: str, quantity: float) -> bool:
        """Валідація продукту"""
        # Перевіряємо назву
        if len(name) < 2 or len(name) > 100:
            return False
        
        # Перевіряємо кількість
        if quantity <= 0 or quantity > 10000:
            return False
        
        # Перевіряємо на стоп-слова
        stop_words = [
            'НАКЛАДНА', 'ДАТА', 'ПЕКАРНЯ', 'ТОВ', 'ПП', 'ФОП', 'РАЗОМ', 'ВСЬОГО',
            'ПРОДАВЕЦЬ', 'ПОКУПЕЦЬ', 'СУМА', 'КІЛЬКІСТЬ', 'ЦІНА', 'ЦЕНА',
            'ПІДПИС', 'ПОДПИС', 'ШТАМП', 'ПЕЧАТЬ', 'НОМЕР', '№', 'N',
            'ТЕЛЕФОН', 'АДРЕСА', 'АДРЕС', 'ІНН', 'ИНН', 'ЄДРПОУ', 'ЕДРПОУ',
            'КІЛЬКІСТЬ', 'НАЗВА', 'КОД', 'ЦІНА', 'СУМА'
        ]
        if any(word in name.upper() for word in stop_words):
            return False
        
        # Перевіряємо на дати та номери
        if re.match(r'^\d{1,2}[.,/-]\d{1,2}[.,/-]\d{2,4}$', name):
            return False
        
        if re.match(r'^№?\d+$', name):
            return False
        
        # Перевіряємо на коди продуктів (тільки цифри)
        if re.match(r'^\d+$', name):
            return False
        
        return True
    
    def calculate_total_quantity(self, products: List[Dict]) -> float:
        """Підрахунок загальної кількості"""
        return sum(product['quantity'] for product in products)
    
    def calculate_total_amount(self, products: List[Dict]) -> float:
        """Підрахунок загальної суми"""
        return sum(product['total'] for product in products)
    
    def process_invoice(self, image_path: str) -> Dict:
        """Повна обробка накладної"""
        logger.info(f"Початок обробки накладної: {image_path}")
        
        # Розпізнаємо текст
        ocr_results = self.extract_text(image_path)
        
        # Витягаємо назву пекарні
        bakery_name = self.extract_bakery_name(ocr_results)
        
        # Витягаємо дані про продукти
        products = self.extract_products_data(ocr_results)
        
        # Підраховуємо підсумки
        total_quantity = self.calculate_total_quantity(products)
        total_amount = self.calculate_total_amount(products)
        
        result = {
            'bakery_name': bakery_name,
            'products': products,
            'total_quantity': total_quantity,
            'total_amount': total_amount,
            'raw_text': [text for _, text, _ in ocr_results],
            'image_path': image_path
        }
        
        logger.info(f"Обробка завершена. Знайдено {len(products)} продуктів")
        return result 