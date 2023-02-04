import json
import time
import datetime
import pytz
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler
from telebot import types
from telebot import TeleBot
from telebot import apihelper

import geopy
from tzwhere import tzwhere


class TimezoneException(ValueError):
    pass


sqlite_database = "sqlite:///bot_base.db"
token = ''
apihelper.API_URL = "http://localhost:8080/bot{0}/{1}"


bot = TeleBot(token)
buttons = {}
TIMEOUT = 200

# logout = bot.log_out()
# print(logout)


# Приветственное сообщение, при переходе по ссылке бота.
@bot.message_handler(commands=['start'])
def start(message):
    markup_inline = types.InlineKeyboardMarkup(row_width=1)
    button1 = types.InlineKeyboardButton(text=buttons["button1"],
                                         callback_data=buttons["button1"])
    markup_inline.add(button1)
    bot.send_message(message.chat.id, message_first_introduction, reply_markup=markup_inline)


# Вступительная часть, описание бота, запрос оплаты, предоставление доступа к "игре", запрос места дислокации.
@bot.callback_query_handler(func=lambda call: True)
def introduction(call):
    # Кнопка "button1" - "ИГРАЕМ?" при нажатии - вступительная часть.
    # В базе данных: добавление пользователя.
    if call.data == buttons["button1"]:
        with Session() as db:
            user = User(user_id=call.from_user.id,
                        user_name=call.from_user.username,
                        full_name=call.from_user.full_name)
            try:
                db.add(user)
                db.commit()
                markup_inline = types.InlineKeyboardMarkup(row_width=1)
                button2 = types.InlineKeyboardButton(text=buttons["button2"],
                                                     callback_data=buttons["button2"])
                markup_inline.add(button2)
                bot.send_message(call.message.chat.id, message_second_introduction, reply_markup=markup_inline)
            except Exception:
                markup_inline = types.InlineKeyboardMarkup(row_width=1)
                button6 = types.InlineKeyboardButton(text=buttons["button6"],
                                                     callback_data=buttons["button6"])
                markup_inline.add(button6)
                bot.send_message(call.message.chat.id, 'Странник, если ты хочешь снова пройти этот путь, '
                                                       'нажми кнопку "СОГЛАСЕН!", и игра в 21 день начнется сначала!',
                                                       reply_markup=markup_inline)
    # Кнопка "button6" - "CОГЛАСЕН" подтверждение пользователем начать "игру" сначала.
    # В базе данных: "обнуление" статусов пользователя.
    elif call.data == buttons["button6"]:
        user_id = call.from_user.id
        with Session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user is not None:
                user.user_day = 0
                user.user_task = 0
                user.user_tz_shift = 0
                db.commit()
                markup_inline = types.InlineKeyboardMarkup(row_width=1)
                button2 = types.InlineKeyboardButton(text=buttons["button2"],
                                                     callback_data=buttons["button2"])
                markup_inline.add(button2)
                bot.send_message(call.message.chat.id, message_second_introduction, reply_markup=markup_inline)
    # Кнопка "button2" - "ПОЛУЧИТЬ ВХОДНОЙ БИЛЕТ" срабатывает после подтверждения перевода администратором.
    # В базе данных: статус "доната" - 1(оплачено), статус "доступа" - 2(доступ получен).
    elif call.data == buttons["button2"]:
        user_id = call.from_user.id
        with Session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user is not None:
                if user.user_donate == 1:
                    user.user_access = 2
                    db.commit()
                else:
                    bot.send_message(call.message.chat.id, "Донейшн пока не обработан, после подтверждения перевода администратором,"
                                                           " тебе придет сообщение по дальнейшим действиям!")
                    return
        with open('days/0. introduction/0. announcement.mp4', 'rb') as f:
            bot.send_video(call.message.chat.id, f, timeout=TIMEOUT, supports_streaming=True)
            time.sleep(5)
            bot.send_message(call.message.chat.id, message_third_introduction)
            time.sleep(10)
            markup_inline = types.InlineKeyboardMarkup(row_width=1)
            button4 = types.InlineKeyboardButton(text=buttons["button4"],
                                                 callback_data=buttons["button4"])
            markup_inline.add(button4)
            bot.send_message(call.message.chat.id, message_rules, reply_markup=markup_inline)
    # Кнопка "button4" - "ПРИНИМАЮ" при нажатии, пользователю приходит последнее вступительное сообщение.
    # В базе данных: статус "доступа" - 3(последняя стадия), статус дня и задачи - 1(переход на 1й день).
    elif call.data == buttons["button4"]:
        user_id = call.from_user.id
        with Session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user is not None:
                user.user_access = 3
                user.user_day = 1
                user.user_task = 0
                db.commit()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        # Кнопка "button5"-"НАПОМИНАНИЯ" появляется рядом с чатом пользователя (правила игры).
        keyboard5 = types.KeyboardButton(buttons['button5'])
        keyboard6 = types.KeyboardButton(buttons['button7'])
        markup.add(keyboard5, keyboard6)
        bot.send_message(call.message.chat.id, message_last_introduction, reply_markup=markup)
    # Кнопка "button3"-"РАЗРЕШИТЬ" появляется в чате у адм., после отправки пользователем подтверждения об оплате.
    elif call.data.startswith(buttons['button3']):
        send_user_id = call.from_user.id
        with Session() as db:
            user = db.query(User).filter(User.user_id == send_user_id).first()
            if user is not None and user.is_admin == 1:
                user_access_id = int(call.data.split('_')[1])
                user = db.query(User).filter(User.user_id == user_access_id).first()
                if user is not None:
                    user.user_donate = 1
                    db.commit()
                    bot.send_message(user_access_id, "Оплата подтверждена, жмите кнопку 'ПОЛУЧИТЬ ВХОДНОЙ БИЛЕТ'.")


# Сохранение и отправка администратору подтверждения оплаты пользователем в виде фото,
# После отправки фото, появляется кнопка в чате у администратора для предоставления доступа.
@bot.message_handler(content_types=['photo'])
def handle_docs_photo(message):
    user_id = message.from_user.id
    with Session() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        admin = db.query(User).filter(User.is_admin == 1).first()

        if user is not None and admin is not None and user.user_donate == 0:
            to_administrator_id = admin.user_id

            try:
                file_id = message.photo[- 1].file_id
                # downloaded_file = bot.download_file(file_info.file_path)
                # src = 'storager/' + message.photo[1].file_id + '.jpg'
                # with open(src, 'wb') as new_file:
                #     new_file.write(downloaded_file)
                bot.reply_to(message, 'Донейшн направлен администратору на проверку! '
                                      'После подтверждения перевода, тебе придет сообщение по дальнейшим действиям!')
            except Exception as e:
                bot.reply_to(message, str(e))

            markup_inline = types.InlineKeyboardMarkup(row_width=1)
            button3 = types.InlineKeyboardButton(text=buttons["button3"],
                                                 callback_data=buttons["button3"] + '_' + str(user_id))
            markup_inline.add(button3)
            bot.send_photo(to_administrator_id, file_id)
            bot.send_message(to_administrator_id, message.chat.id, reply_markup=markup_inline)


# Сохранение и отправка администратору подтверждения оплаты пользователем в виде документа,
# После отправки документа, появляется кнопка в чате у администратора для предоставления доступа.
@bot.message_handler(content_types=['document'])
def handle_docs_document(message):
    user_id = message.from_user.id
    with Session() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        admin = db.query(User).filter(User.is_admin == 1).first()

        if user is not None and admin is not None and user.user_donate == 0:
            to_administrator_id = admin.user_id

            try:
                file_id = message.document.file_id
                # downloaded_file = bot.download_file(file_info.file_path)
                # src = 'storager/' + message.document.file_id
                # with open(src, 'wb') as new_file:
                #     new_file.write(downloaded_file)
                bot.reply_to(message, 'Донейшн направлен администратору на проверку! '
                                      'После подтверждения перевода, тебе придет сообщение по дальнейшим действиям!')
            except Exception as e:
                bot.reply_to(message, str(e))
            markup_inline = types.InlineKeyboardMarkup(row_width=1)
            button3 = types.InlineKeyboardButton(text=buttons["button3"],
                                                 callback_data=buttons["button3"] + '_' + str(message.chat.id))
            markup_inline.add(button3)
            bot.send_document(to_administrator_id, file_id)
            bot.send_message(to_administrator_id, message.chat.id, reply_markup=markup_inline)


# Проверка алгоритма - контента по дням.
def test_function(user_id):
    user_day = 1
    current_stage = 0
    while True:
        user_day, current_stage = send_game_message(user_id, current_stage, user_day)
        if user_day == 22 and current_stage == 3:
            break
        time.sleep(5)


# Обработчик названия города
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    with Session() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is not None:
            if text == buttons['button5']:
                bot.send_message(message.chat.id, message_rules)
            elif text == 'test1':
                if user.is_admin:
                    test_function(user_id)
            # Добавление, изменение и проверка администратора.
            elif text == 'admin1234':
                if user.is_admin:
                    bot.send_message(user_id, 'Вы уже администратор.')
                else:
                    users = db.query(User).filter(User.is_admin==1).all()
                    for old_admin in users:
                        old_admin.is_admin = 0
                    user.is_admin = 1
                    db.commit()
                    bot.send_message(user_id, 'Изменения внесены.')
            elif user.user_access == 3 or user.user_access == 2:
                try:
                    tz_min = get_timezone(bot, user_id, text)
                except TimezoneException as e:
                    bot.send_message(user_id, str(e))
                    return
                user.user_tz_shift = tz_min
                db.commit()
                if user.user_day == 0:
                    bot.send_message(user_id, 'Сонастройка выполнена, играем ✨'
                                              '\nНаш первый день начнётся завтра, удачи! 💚')
                    user.user_day = 1
                    db.commit()
                else:
                    bot.send_message(user_id, 'Поздравляю со сменой локации своего бренного тела!')


# Запрос места дислокации у пользователя, для сохранения часового пояса в базе данных.
def get_timezone(bot, chat_id, city):
    geo = geopy.geocoders.Nominatim(user_agent="SuperMon_Bot")
    location = geo.geocode(city)
    if location is None:
        raise TimezoneException("Не удалось найти такой город, попробуйте написать его название латиницей, "
                                "или указать более крупный город поблизости.")
    else:
        tzw = tzwhere.tzwhere()
        timezone_str = tzw.tzNameAt(location.latitude, location.longitude)  # получаем название часового пояса
        tz = pytz.timezone(timezone_str)
        tz_info = datetime.datetime.now(tz=tz).strftime("%z")  # получаем смещение часового пояса
        tz_info = tz_info[0:3] + ":" + tz_info[3:]  # приводим к формату ±ЧЧ:ММ
        bot.send_message(chat_id, "Часовой пояс установлен в %s (%s от GMT)." % (timezone_str, tz_info))
        tz_min = int(tz_info[0:3])*60 + int(tz_info[4:])
        # здесь должно быть сохранение выбранной строки в БД
        return tz_min


# Загрузка текста для каждого дня (текст - сообщения, кнопки):
if __name__ == '__main__':
    with open('buttons.json', encoding='utf-8-sig') as f:
        buttons = json.load(f)
    with open('days/0. introduction/0. first_introduction.txt', encoding='utf-8') as f:
        message_first_introduction = f.read()
    with open('days/0. introduction/0. second_introduction.txt', encoding='utf-8') as f:
        message_second_introduction = f.read()
    with open('days/0. introduction/0. third_introduction.txt', encoding='utf-8') as f:
        message_third_introduction = f.read()
    with open('days/0. introduction/0. rules of the game.txt', encoding='utf-8') as f:
        message_rules = f.read()
    with open('days/0. introduction/0. last_introduction.txt', encoding='utf-8') as f:
        message_last_introduction = f.read()
    with open('days/★. reminder3.txt', encoding='utf-8') as f:
        message_reminder_3 = f.read()
    with open('days/1_day/1. main_text.txt', encoding='utf-8') as f:
        message_1 = f.read()
    with open('days/1_day/1. reminder1.txt', encoding='utf-8') as f:
        message_1_1 = f.read()
    with open('days/1_day/1. reminder2.txt', encoding='utf-8') as f:
        message_1_2 = f.read()
    with open('days/2_day/2. main_text.txt', encoding='utf-8') as f:
        message_2 = f.read()
    with open('days/2_day/2. reminder1.txt', encoding='utf-8') as f:
        message_2_1 = f.read()
    with open('days/2_day/2. reminder2.txt', encoding='utf-8') as f:
        message_2_2 = f.read()
    with open('days/3_day/3. main_text.txt', encoding='utf-8') as f:
        message_3 = f.read()
    with open('days/3_day/3. reminder1.txt', encoding='utf-8') as f:
        message_3_1 = f.read()
    with open('days/3_day/3. reminder2.txt', encoding='utf-8') as f:
        message_3_2 = f.read()
    with open('days/4_day/4. main_text.txt', encoding='utf-8') as f:
        message_4 = f.read()
    with open('days/4_day/4. reminder1.txt', encoding='utf-8') as f:
        message_4_1 = f.read()
    with open('days/4_day/4. reminder2.txt', encoding='utf-8') as f:
        message_4_2 = f.read()
    with open('days/5_day/5. main_text.txt', encoding='utf-8') as f:
        message_5 = f.read()
    with open('days/5_day/5. reminder1.txt', encoding='utf-8') as f:
        message_5_1 = f.read()
    with open('days/5_day/5. reminder2.txt', encoding='utf-8') as f:
        message_5_2 = f.read()
    with open('days/6_day/6. main_text.txt', encoding='utf-8') as f:
        message_6 = f.read()
    with open('days/6_day/6. reminder1.txt', encoding='utf-8') as f:
        message_6_1 = f.read()
    with open('days/6_day/6. reminder2.txt', encoding='utf-8') as f:
        message_6_2 = f.read()
    with open('days/7_day/7. main_text.txt', encoding='utf-8') as f:
        message_7 = f.read()
    with open('days/7_day/7. reminder1.txt', encoding='utf-8') as f:
        message_7_1 = f.read()
    with open('days/8_day/8. main_text.txt', encoding='utf-8') as f:
        message_8 = f.read()
    with open('days/8_day/8. reminder1.txt', encoding='utf-8') as f:
        message_8_1 = f.read()
    with open('days/8_day/8. reminder2.txt', encoding='utf-8') as f:
        message_8_2 = f.read()
    with open('days/8_day/8. reminder3.txt', encoding='utf-8') as f:
        message_8_3 = f.read()
    with open('days/9_day/9. main_text.txt', encoding='utf-8') as f:
        message_9 = f.read()
    with open('days/9_day/9. reminder1.txt', encoding='utf-8') as f:
        message_9_1 = f.read()
    with open('days/9_day/9. reminder2.txt', encoding='utf-8') as f:
        message_9_2 = f.read()
    with open('days/10_day/10. main_text.txt', encoding='utf-8') as f:
        message_10 = f.read()
    with open('days/10_day/10. reminder1.txt', encoding='utf-8') as f:
        message_10_1 = f.read()
    with open('days/10_day/10. reminder2.txt', encoding='utf-8') as f:
        message_10_2 = f.read()
    with open('days/11_day/11. main_text.txt', encoding='utf-8') as f:
        message_11 = f.read()
    with open('days/11_day/11. reminder1.txt', encoding='utf-8') as f:
        message_11_1 = f.read()
    with open('days/11_day/11. reminder2.txt', encoding='utf-8') as f:
        message_11_2 = f.read()
    with open('days/12_day/12. main_text.txt', encoding='utf-8') as f:
        message_12 = f.read()
    with open('days/12_day/12. reminder1.txt', encoding='utf-8') as f:
        message_12_1 = f.read()
    with open('days/12_day/12. reminder2.txt', encoding='utf-8') as f:
        message_12_2 = f.read()
    with open('days/13_day/13. main_text.txt', encoding='utf-8') as f:
        message_13 = f.read()
    with open('days/13_day/13. reminder1.txt', encoding='utf-8') as f:
        message_13_1 = f.read()
    with open('days/13_day/13. reminder2.txt', encoding='utf-8') as f:
        message_13_2 = f.read()
    with open('days/14_day/14. main_text.txt', encoding='utf-8') as f:
        message_14 = f.read()
    with open('days/14_day/14. reminder1.txt', encoding='utf-8') as f:
        message_14_1 = f.read()
    with open('days/14_day/14. reminder2.txt', encoding='utf-8') as f:
        message_14_2 = f.read()
    with open('days/15_day/15. main_text.txt', encoding='utf-8') as f:
        message_15 = f.read()
    with open('days/15_day/15. reminder1.txt', encoding='utf-8') as f:
        message_15_1 = f.read()
    with open('days/15_day/15. reminder2.txt', encoding='utf-8') as f:
        message_15_2 = f.read()
    with open('days/16_day/16. main_text.txt', encoding='utf-8') as f:
        message_16 = f.read()
    with open('days/16_day/16. reminder1.txt', encoding='utf-8') as f:
        message_16_1 = f.read()
    with open('days/16_day/16. reminder2.txt', encoding='utf-8') as f:
        message_16_2 = f.read()
    with open('days/17_day/17. main_text.txt', encoding='utf-8') as f:
        message_17 = f.read()
    with open('days/17_day/17. reminder1.txt', encoding='utf-8') as f:
        message_17_1 = f.read()
    with open('days/17_day/17. reminder2.txt', encoding='utf-8') as f:
        message_17_2 = f.read()
    with open('days/18_day/18. main_text.txt', encoding='utf-8') as f:
        message_18 = f.read()
    with open('days/18_day/18. reminder1.txt', encoding='utf-8') as f:
        message_18_1 = f.read()
    with open('days/18_day/18. reminder2.txt', encoding='utf-8') as f:
        message_18_2 = f.read()
    with open('days/19_day/19. main_text.txt', encoding='utf-8') as f:
        message_19 = f.read()
    with open('days/19_day/19. reminder1.txt', encoding='utf-8') as f:
        message_19_1 = f.read()
    with open('days/20_day/20. main_text.txt', encoding='utf-8') as f:
        message_20 = f.read()
    with open('days/20_day/20. reminder1.txt', encoding='utf-8') as f:
        message_20_1 = f.read()
    with open('days/21_day/21. main_text.txt', encoding='utf-8') as f:
        message_21 = f.read()
    with open('days/21_day/21. reminder1.txt', encoding='utf-8') as f:
        message_21_1 = f.read()
    with open('days/22_day_(last_day)/22. reminder2.txt', encoding='utf-8') as f:
        message_22_2 = f.read()
    with open('days/22_day_(last_day)/22. reminder3.txt', encoding='utf-8') as f:
        message_22_3 = f.read()

# Создание базы данных:
    Base = declarative_base()
    engine = create_engine(sqlite_database)


    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True, index=True)
        user_id = Column(Integer, unique=True)
        user_name = Column(String, default="")
        full_name = Column(String, default="")
        is_admin = Column(Integer, default=0)
        user_donate = Column(Integer, default=0)
        user_access = Column(Integer, default=0)
        user_day = Column(Integer, default=0)
        user_task = Column(Integer, default=0)
        user_tz_shift = Column(Integer, default=0)


    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autoflush=False, bind=engine)


# Формирование, распределение и отправка контента по дням.
def send_game_message(user_id, current_stage, user_day):
    if user_day == 1:
        if current_stage == 0:
            with open('days/1_day/1. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ПЕРВЫЙ\nОбразный…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/1_day/1. ДЕНЬ ПЕРВЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_1)
                time.sleep(10)
                bot.send_message(user_id, message_reminder_3)
            return 1, 1
        elif current_stage == 1:
            with open('days/1_day/1. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f)
            with open('days/1_day/1. МГНОВЕННАЯ ОСТАНОВКА МЫСЛЕЙ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_1_1)
            return 1, 3
        elif current_stage == 3:
            with open('days/1_day/СУТЬ РЕАЛЬНОСТИ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_1_2)
            return 2, 0
    elif user_day == 2:
        if current_stage == 0:
            with open('days/2_day/2. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ВТОРОЙ\nПреображение…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/2_day/2. ДЕНЬ ВТОРОЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_2)
            return 2, 1
        elif current_stage == 1:
            with open('days/2_day/2. reminder1.jpg', 'rb') as f:
                bot.send_photo(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_2_1)
            return 2, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_2_2)
            return 3, 0
    elif user_day == 3:
        if current_stage == 0:
            with open('days/3_day/3. main.MOV', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ТРЕТИЙ\nВнутренняя трансформация…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/3_day/3. ДЕНЬ ТРЕТИЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_3)
            return 3, 1
        elif current_stage == 1:
            with open('days/3_day/3. reminder1.MOV', 'rb') as f:
                bot.send_video(user_id, f, timeout=TIMEOUT, supports_streaming=True)
                bot.send_message(user_id, message_3_1)
            return 3, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_3_2)
            return 4, 0
    elif user_day == 4:
        if current_stage == 0:
            with open('days/4_day/4. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ЧЕТВЁРТЫЙ\nВеликолепный…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/4_day/4. ДЕНЬ ЧЕТВЁРТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_4)
            return 4, 1
        elif current_stage == 1:
            with open('days/4_day/4. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, timeout=TIMEOUT, supports_streaming=True)
                bot.send_message(user_id, message_4_1)
            return 4, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_4_2)
            return 5, 0
    elif user_day == 5:
        if current_stage == 0:
            with open('days/5_day/5. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ПЯТЫЙ\nЯ твой друг…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/5_day/5.1 ДЕНЬ ПЯТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_5)
            with open('days/5_day/5.2 комментарий к заданию.ogg', 'rb') as f:
                bot.send_audio(user_id, f, caption='♡ Комментарий к заданию.', timeout=TIMEOUT)
            return 5, 1
        elif current_stage == 1:
            with open('days/5_day/5. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, timeout=TIMEOUT, supports_streaming=True)
                bot.send_message(user_id, message_5_1)
            return 5, 2
        elif current_stage == 2:
            with open('days/5_day/5. reminder2.jpg', 'rb') as f:
                bot.send_photo(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_5_2)
            return 6, 0
    elif user_day == 6:
        if current_stage == 0:
            with open('days/6_day/6. main.MOV', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ШЕСТОЙ\nОщущаем изобилие…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/6_day/6. ДЕНЬ ШЕСТОЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_6)
            return 6, 1
        elif current_stage == 1:
            bot.send_message(user_id, message_6_1)
            return 6, 2
        elif current_stage == 2:
            with open('days/6_day/6. reminder2.jpg', 'rb') as f:
                bot.send_photo(user_id, f, caption=message_6_2, timeout=TIMEOUT)
                bot.send_message(user_id, message_6_2)
            return 7, 0
    elif user_day == 7:
        if current_stage == 0:
            with open('days/7_day/7. main.MOV', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ СЕДЬМОЙ\n...', timeout=TIMEOUT, supports_streaming=True)
            with open('days/7_day/7. ДЕНЬ СЕДЬМОЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_7)
            return 7, 1
        elif current_stage == 1:
            with open('days/7_day/7. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, timeout=TIMEOUT, supports_streaming=True)
                bot.send_message(user_id, message_7_1)
            return 8, 0
    elif user_day == 8:
        if current_stage == 0:
            bot.send_message(user_id, "ДЕНЬ ВОСЬМОЙ\nГармония…")
            with open('days/8_day/8. ДЕНЬ ВОСЬМОЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_8)
            return 8, 1
        elif current_stage == 1:
            with open('days/8_day/8. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, timeout=TIMEOUT, supports_streaming=True)
                bot.send_message(user_id, message_8_1)
            return 8, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_8_2)
            return 8, 3
        elif current_stage == 3:
            with open('days/8_day/8. reminder3.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_8_3, timeout=1000, supports_streaming=True)
            return 9, 0
    elif user_day == 9:
        if current_stage == 0:
            with open('days/9_day/9. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ДЕВЯТЫЙ\nВолшебный…', timeout=TIMEOUT, supports_streaming=True)
            with open('days/9_day/9. ДЕНЬ ДЕВЯТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_9)
            return 9, 1
        elif current_stage == 1:
            with open('days/9_day/9. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, timeout=TIMEOUT, supports_streaming=True)
                bot.send_message(user_id, message_9_1)

            return 9, 2
        elif current_stage == 2:
            with open('days/9_day/9. reminder2.jpg', 'rb') as f:
                bot.send_photo(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_9_2)
            return 10, 0
    elif user_day == 10:
        if current_stage == 0:
            with open('days/10_day/10. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ДЕСЯТЫЙ\nВысвобождающий…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/10_day/10. ДЕНЬ ДЕСЯТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_10)
            return 10, 1
        elif current_stage == 1:
            with open('days/10_day/10. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_10_1, timeout=TIMEOUT, supports_streaming=True)
            return 10, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_10_2)
            return 11, 0
    elif user_day == 11:
        if current_stage == 0:
            with open('days/11_day/11 main.MOV', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ОДИННАДЦАТЫЙ\nЛюбовь…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/11_day/11. ДЕНЬ ОДИННАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_11)
                return 11, 1
        elif current_stage == 1:
            with open('days/11_day/11. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_11_1, timeout=TIMEOUT, supports_streaming=True)
                return 11, 2
        elif current_stage == 2:
            with open('days/11_day/11. reminder2.jpg', 'rb') as f:
                bot.send_photo(user_id, f, caption=message_11_2, timeout=TIMEOUT)
            return 12, 0
    elif user_day == 12:
        if current_stage == 0:
            with open('days/12_day/12. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ДВЕНАДЦАТЫЙ\nПрекрасный…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/12_day/12. ДЕНЬ ДВЕНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_12)
            return 12, 1
        elif current_stage == 1:
            with open('days/12_day/12. reminder1.jpg', 'rb') as f:
                bot.send_photo(user_id, f, caption=message_12_1, timeout=TIMEOUT)
            return 12, 2
        elif current_stage == 2:
            with open('days/12_day/12. reminder2.MOV', 'rb') as f:
                bot.send_video(user_id, f, caption=message_12_2, timeout=TIMEOUT, supports_streaming=True)
            return 13, 0
    elif user_day == 13:
        if current_stage == 0:
            with open('days/13_day/13. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ТРИНАДЦАТЫЙ\nВкусный…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/13_day/13. ДЕНЬ ТРИНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_13)
            return 13, 1
        elif current_stage == 1:
            with open('days/13_day/13. reminder1.jpg', 'rb') as f:
                bot.send_photo(user_id, f, caption=message_13_1, timeout=TIMEOUT)
            return 13, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_13_2)
            return 14, 0
    elif user_day == 14:
        if current_stage == 0:
            with open('days/14_day/14. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ЧЕТЫРНАДЦАТЫЙ\nЗамечтательный…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/14_day/14. ДЕНЬ ЧЕТЫРНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_14)
            return 14, 1
        elif current_stage == 1:
            with open('days/14_day/14. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_14_1, timeout=TIMEOUT, supports_streaming=True)
            return 14, 2
        elif current_stage == 2:
            bot.send_message(user_id, message_14_2)
            return 15, 0
    elif user_day == 15:
        if current_stage == 0:
            with open('days/15_day/15. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ПЯТНАДЦАТЫЙ\nЧувственный…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/15_day/15. ДЕНЬ ПЯТНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_15)
            return 15, 1
        elif current_stage == 1:
            with open('days/15_day/15. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_15_1, timeout=TIMEOUT, supports_streaming=True)
            return 15, 2
        elif current_stage == 2:
            with open('days/15_day/15. reminder2.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_15_2, timeout=TIMEOUT, supports_streaming=True)
            return 16, 0
    elif user_day == 16:
        if current_stage == 0:
            with open('days/16_day/16. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ШЕСТНАДЦАТЫЙ\nКрасивый…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/16_day/16. ДЕНЬ ШЕСТНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_16)
            return 16, 1
        elif current_stage == 1:
            with open('days/16_day/16. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_16_1, timeout=TIMEOUT, supports_streaming=True)
            return 16, 2
        elif current_stage == 2:
            bot. send_message(user_id, message_16_2)
            return 17, 0
    elif user_day == 17:
        if current_stage == 0:
            with open('days/17_day/17. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ СЕМНАДЦАТЫЙ\nТворческий…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/17_day/17. ДЕНЬ СЕМНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_17)
            return 17, 1
        elif current_stage == 1:
            bot.send_message(user_id, message_17_1)
            return 17, 2
        elif current_stage == 2:
            with open('days/17_day/17. reminder2.jpg', 'rb') as f:
                bot.send_photo(user_id, f, caption=message_17_2, timeout=TIMEOUT)
            return 18, 0
    elif user_day == 18:
        if current_stage == 0:
            with open('days/18_day/18. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ВОСЕМНАДЦАТЫЙ\nТы Увидишь…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/18_day/18. ДЕНЬ ВОСЕМНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_18)
            return 18, 1
        elif current_stage == 1:
            bot.send_message(user_id, message_18_1)
            return 18, 2
        elif current_stage == 2:
            with open('days/18_day/18. reminder2.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption=message_18_2, timeout=TIMEOUT, supports_streaming=True)
            return 19, 0
    elif user_day == 19:
        if current_stage == 0:
            with open('days/19_day/19. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ДЕВЯТНАДЦАТЫЙ\nИнтересный…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/19_day/19. ДЕНЬ ДЕВЯТНАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_19)
            return 19, 1
        elif current_stage == 1:
            with open('days/19_day/19. reminder1.MOV', 'rb') as f:
                bot.send_video(user_id, f, caption=message_19_1, timeout=TIMEOUT, supports_streaming=True)
            return 20, 0
    elif user_day == 20:
        if current_stage == 0:
            with open('days/20_day/20. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ДВАДЦАТЫЙ\nЗамечательный…всё замечательней и изобильней…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/20_day/20. ДЕНЬ ДВАДЦАТЫЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_20)
            return 20, 1
        elif current_stage == 1:
            bot.send_message(user_id, message_20_1)
            return 21, 0
    elif user_day == 21:
        if current_stage == 0:
            with open('days/21_day/21. main.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='ДЕНЬ ДВАДЦАТЬ ПЕРВЫЙ\nСолнечный…расширяющий…',
                               timeout=TIMEOUT, supports_streaming=True)
            with open('days/21_day/21. ДЕНЬ_ДВАДЦАТЬ_ПЕРВЫЙ_Я_ВСЁ_МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_21)
            return 21, 1
        elif current_stage == 1:
            bot.send_message(user_id, message_21_1)
            return 22, 1
    elif user_day == 22:
        if current_stage == 1:
            with open('days/22_day_(last_day)/22. reminder1.mp4', 'rb') as f:
                bot.send_video(user_id, f, caption='Хорошая песня…об особенном чувстве, которое сложно описать 😉',
                               timeout=TIMEOUT, supports_streaming=True)
            return 22, 2
        elif current_stage == 2:
            with open('days/22_day_(last_day)/22. ВЫПУСКНОЙ. Я ВСЁ МОГУ.mp3', 'rb') as f:
                bot.send_audio(user_id, f, timeout=TIMEOUT)
                bot.send_message(user_id, message_22_2)
            return 22, 3
        elif current_stage == 3:
            bot.send_message(user_id, message_22_3)
            return


# Сверка времени, отправка сообщений
# В базе данных: записывает следующий день и стадию.
def tick():
    dt = datetime.datetime.now(datetime.timezone.utc)
    utc_hour = dt.hour
    with Session() as db:
        users = db.query(User).filter(User.user_access == 3).all()
        for user in users:
            user_bias = user.user_tz_shift // 60
            user_hour = utc_hour + user_bias
            stage_dict = {5: 0, 12: 1, 18: 2, 20: 3}
            current_stage = stage_dict.get(user_hour, -1)
            if current_stage == -1:
                continue
            if user.user_task == current_stage:
                user_day = user.user_day
                user_id = user.user_id
                next_day, next_stage = send_game_message(user_id, current_stage, user_day)
                user.user_day = next_day
                user.user_task = next_stage
                db.commit()


scheduler = BackgroundScheduler()
scheduler.add_job(tick, CronTrigger.from_crontab('38 * * * *', timezone='GMT'), id="tick")
scheduler.start()


bot.infinity_polling()
