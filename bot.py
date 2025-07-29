import logging
import os
import time
from datetime import datetime
from typing import Dict, List

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN, PHOTO_GROUPING_TIMEOUT
from ocr_processor import OCRProcessor
from excel_generator import ExcelGenerator
from training_data_collector import TrainingDataCollector

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class NakladniBot:
    def __init__(self):
        # Словник для зберігання фото в очікуванні
        self.pending_photos: Dict[int, Dict] = {}
        
        # Створюємо папку для фото, якщо її немає
        self.photos_dir = "nakladni_photos"
        if not os.path.exists(self.photos_dir):
            os.makedirs(self.photos_dir)
            logger.info(f"Створено папку: {self.photos_dir}")
        
        # Ініціалізуємо OCR та Excel генератор
        self.ocr_processor = OCRProcessor()
        self.excel_generator = ExcelGenerator()
        self.training_collector = TrainingDataCollector()
        
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка фото накладної"""
        user_id = update.effective_user.id
        photo = update.message.photo[-1]  # Найбільша версія фото
        
        try:
            # Завантажуємо фото
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()
            
            # Зберігаємо фото в окремій папці
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_filename = os.path.join(self.photos_dir, f"photo_{user_id}_{timestamp}.jpg")
            
            with open(photo_filename, 'wb') as f:
                f.write(photo_bytes)
            
            # Перевіряємо, чи є вже фото від цього користувача
            if user_id in self.pending_photos:
                # Друге фото - обробляємо накладну
                await self.process_nakladna(user_id, photo_filename, update, context)
            else:
                # Перше фото - зберігаємо і чекаємо друге
                self.pending_photos[user_id] = {
                    'photo1': photo_filename,
                    'timestamp': time.time()
                }
                await update.message.reply_text("✅ Фото 1 збережено\n⏳ Очікую фото 2... (у вас є 5 хвилин)")
                
                # Запускаємо таймер для очищення (якщо job_queue доступний)
                if hasattr(context, 'job_queue') and context.job_queue:
                    context.job_queue.run_once(
                        self.cleanup_pending_photo, 
                        PHOTO_GROUPING_TIMEOUT, 
                        data=user_id
                    )
                
        except Exception as e:
            logger.error(f"Помилка обробки фото: {e}")
            await update.message.reply_text("❌ Помилка обробки фото. Спробуйте ще раз.")
    
    async def process_nakladna(self, user_id: int, photo2_filename: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка повної накладної (2 фото) з OCR та Excel"""
        try:
            photo1_filename = self.pending_photos[user_id]['photo1']
            
            # Повідомляємо про початок обробки
            await update.message.reply_text("🔄 Обробляю накладну... (це може зайняти кілька секунд)")
            
            # Обробляємо обидва фото через OCR
            invoice_data1 = self.ocr_processor.process_invoice(photo1_filename)
            invoice_data2 = self.ocr_processor.process_invoice(photo2_filename)
            
            # Зберігаємо сирий текст для аналізу
            self.save_raw_ocr_text(photo1_filename, invoice_data1['raw_text'])
            self.save_raw_ocr_text(photo2_filename, invoice_data2['raw_text'])
            
            # Зберігаємо дані для тренування
            invoice_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            combined_results = {
                'bakery_name': invoice_data1.get('bakery_name') or invoice_data2.get('bakery_name'),
                'products': invoice_data1.get('products', []) + invoice_data2.get('products', []),
                'total_quantity': invoice_data1.get('total_quantity', 0) + invoice_data2.get('total_quantity', 0),
                'total_amount': invoice_data1.get('total_amount', 0) + invoice_data2.get('total_amount', 0)
            }
            
            training_dir = self.training_collector.save_invoice_data(
                invoice_id, photo1_filename, photo2_filename,
                invoice_data1['raw_text'], invoice_data2['raw_text'],
                combined_results
            )
            
            # Об'єднуємо дані з обох фото
            combined_products = combined_results['products']
            bakery_name = combined_results['bakery_name']
            
            # Створюємо Excel файл
            current_date = datetime.now().strftime("%d.%m")
            excel_filepath = self.excel_generator.create_excel(bakery_name, combined_products, current_date)
            
            # Створюємо звіт
            report_filename = f"Накладна_{current_date}.txt"
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(f"НАКЛАДНА - {current_date}\n")
                f.write("=" * 50 + "\n")
                f.write(f"Пекарня: {bakery_name or 'Невідома'}\n")
                f.write(f"Фото 1: {photo1_filename}\n")
                f.write(f"Фото 2: {photo2_filename}\n")
                f.write(f"Excel файл: {excel_filepath}\n")
                f.write(f"Час обробки: {datetime.now().strftime('%H:%M:%S')}\n")
                f.write("=" * 50 + "\n")
                f.write(f"Знайдено продуктів: {len(combined_products)}\n")
                f.write(f"Загальна кількість: {sum(p.get('quantity', 0) for p in combined_products):.2f}\n")
                f.write(f"Загальна сума: {sum(p.get('total', 0) for p in combined_products):.2f}\n")
                f.write("=" * 50 + "\n")
                f.write("СПИСОК ПРОДУКТІВ:\n")
                for i, product in enumerate(combined_products, 1):
                    f.write(f"{i}. {product.get('name', 'Невідомий продукт')} - "
                           f"{product.get('quantity', 0)} шт. - "
                           f"{product.get('total', 0):.2f} грн.\n")
            
            # Відправляємо результат
            result_message = (
                f"✅ Накладна оброблена!\n\n"
                f"🏪 Пекарня: {bakery_name or 'Невідома'}\n"
                f"📦 Продуктів: {len(combined_products)}\n"
                f"📊 Загальна кількість: {sum(p.get('quantity', 0) for p in combined_products):.2f}\n"
                f"💰 Загальна сума: {sum(p.get('total', 0) for p in combined_products):.2f} грн.\n\n"
                f"📄 Звіт: {report_filename}\n"
                f"📊 Excel: {os.path.basename(excel_filepath)}\n"
                f"📸 Фото збережено в папці: {self.photos_dir}\n\n"
                f"🎯 Дані збережено для тренування: {training_dir}\n"
                f"💡 Для покращення точності відредагуйте файл manual_annotation.json"
            )
            
            await update.message.reply_text(result_message)
            
            # Очищаємо дані користувача
            del self.pending_photos[user_id]
            
        except Exception as e:
            logger.error(f"Помилка обробки накладної: {e}")
            await update.message.reply_text(
                "❌ Помилка обробки накладної. Спробуйте ще раз.\n"
                "Переконайтеся, що фото чіткі та містять текст накладних."
            )
    
    def save_raw_ocr_text(self, image_path: str, raw_text: List[str]):
        """Збереження сирого тексту OCR для аналізу"""
        try:
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            raw_text_filename = f"raw_text_{base_name}.txt"
            
            with open(raw_text_filename, 'w', encoding='utf-8') as f:
                f.write(f"СИРИЙ ТЕКСТ OCR: {image_path}\n")
                f.write("=" * 50 + "\n")
                for i, text in enumerate(raw_text, 1):
                    f.write(f"{i:3d}. {text}\n")
            
            logger.info(f"Збережено сирий текст OCR: {raw_text_filename}")
        except Exception as e:
            logger.error(f"Помилка збереження сирого тексту: {e}")
    
    async def cleanup_pending_photo(self, context: ContextTypes.DEFAULT_TYPE):
        """Очищення застарілих фото"""
        user_id = context.job.data
        if user_id in self.pending_photos:
            photo_filename = self.pending_photos[user_id]['photo1']
            self.cleanup_temp_files([photo_filename])
            del self.pending_photos[user_id]
            logger.info(f"Очищено застаріле фото для користувача {user_id}")
    
    def cleanup_temp_files(self, filenames: List[str]):
        """Видалення тимчасових файлів"""
        for filename in filenames:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                logger.error(f"Помилка видалення файлу {filename}: {e}")

def main():
    """Запуск бота"""
    bot = NakladniBot()
    
    # Створюємо додаток з job_queue
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Додаємо обробник фото
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    
    # Запускаємо бота
    logger.info("Бот запущений з системою тренування OCR!")
    logger.info("Надішліть фото накладної для тестування та збору даних.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 