# main.py
import asyncio
import logging
import os
import zipfile
import gzip
import shutil
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message
import config

logging.basicConfig(level=logging.INFO)

session = AiohttpSession(api=TelegramAPIServer.from_base(config.API_SERVER))
bot = Bot(token=config.BOT_TOKEN, session=session)
dp = Dispatcher()

TEMP_DIR = "temp_stickers"
os.makedirs(TEMP_DIR, exist_ok=True)

@dp.message(F.document)
async def handle_zip(message: Message):
    if message.from_user.id != config.OWNER_ID:
        return

    doc = message.document
    if not doc.file_name.endswith('.zip'):
        await message.reply("⚠️ Пришли мне ZIP-архив с файлами .tgs или .json.")
        return

    status_msg = await message.reply("⏳ Скачиваю и распаковываю архив...")
    
    try:
        file = await bot.get_file(doc.file_id)
        zip_path = os.path.join(TEMP_DIR, doc.file_name)
        await bot.download_file(file.file_path, zip_path)

        extract_path = os.path.join(TEMP_DIR, f"extracted_{message.from_user.id}")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        tgs_files = []
        json_files = []
        
        for root, dirs, files in os.walk(extract_path):
            for f in files:
                if f.endswith('.tgs'):
                    tgs_files.append(os.path.join(root, f))
                elif f.endswith('.json'):
                    json_files.append(os.path.join(root, f))

        # Конвертация JSON в TGS
        for js in json_files:
            tgs_path = js.replace('.json', '.tgs')
            with open(js, 'rb') as f_in:
                with gzip.open(tgs_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            tgs_files.append(tgs_path)

        if not tgs_files:
            await status_msg.edit_text("❌ В архиве не найдено .tgs или .json файлов.")
            return

        bot_username = (await bot.me()).username
        pack_name = f"pack_{message.from_user.id}_by_{bot_username}"
        
        first_sticker_path = tgs_files[0]
        
        try:
            with open(first_sticker_path, 'rb') as f:
                await bot.create_new_sticker_set(
                    user_id=message.from_user.id,
                    name=pack_name,
                    title=f"Пак {message.from_user.first_name}",
                    stickers=[{"sticker": f, "format": "animated", "emoji_list": ["😀"]}],
                    sticker_format="animated"
                )
            
            link = f"https://t.me/addstickers/{pack_name}"
            await status_msg.edit_text(
                f"✅ <b>Пак успешно создан!</b>\n\n"
                f"🔗 <a href='{link}'>Нажми сюда, чтобы добавить</a>\n\n"
                f"(Файлов распаковано: {len(tgs_files)})",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logging.error(f"Ошибка создания пака: {e}")
            with open(first_sticker_path, 'rb') as f:
                await message.reply_document(
                    f, 
                    caption=f"⚠️ Не удалось создать пак (Мисуграм не поддерживает).\n"
                            f"Распаковано файлов: {len(tgs_files)}"
                )

    except Exception as e:
        logging.error(f"Общая ошибка: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка: {e}")
    
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

async def main():
    logging.info("🚀 Бот-распаковщик стикеров запущен.")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())