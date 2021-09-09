import logging
import multiprocessing
import os
import threading
from time import sleep
from flask import Flask, Response

import telebot
from requests import exceptions

from linkedin_bot import main, Linkedin

logging.basicConfig(level=logging.INFO, filename='app.log',
                    format='%(process)d - %(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

TOKEN = os.getenv('BOT_TOKEN')
if TOKEN is None:
    logging.warning("Не найден BOT_TOKEN в системных переменных.")
    TOKEN = '1609817028:AAG-9H2NRj4lyUDCNoJt8znfR_0Eqw1cc3c'

if __name__ == '__main__':
    bot = telebot.TeleBot(TOKEN)
    INSTANCES = {}


    def bot_send_message(chat_id, text):
        keyboard = telebot.types.ReplyKeyboardMarkup(True)
        keyboard.row("Начать поиск", "Завершить поиск")
        try:
            bot.send_message(chat_id, text, reply_markup=keyboard)
        except exceptions.ConnectionError:
            sleep(3)
            logging.info("Пытаемся отправить сообщение...")
            bot_send_message(chat_id, text)


    def q_output_waiter():
        while True:
            for linkedin, _ in INSTANCES.values():
                q_output = linkedin.queue_output
                if not q_output.empty():
                    message = q_output.get()
                    bot_send_message(linkedin.chat_id, message)
                    logging.info("Исходящее сообщение: " + message)
            sleep(0.1)


    def q_output_kmd_waiter():
        while True:
            delete_inst = []
            for linkedin, proc in INSTANCES.values():
                q_kmd_out = linkedin.queue_kmd_output
                if not q_kmd_out.empty():
                    message = q_kmd_out.get()
                    if message == "_kmd_chat_bot_exit_is_ok":
                        delete_inst.append((linkedin.chat_id, proc))

            for chat_id, proc in delete_inst:
                bot_send_message(chat_id, "Поиск завершен")
                proc.terminate()
                del INSTANCES[chat_id]
                logging.info('Процесс поиска завершен')
            sleep(0.1)


    def start(chat_id):
        linkedin = Linkedin(chat_id)
        proc = multiprocessing.Process(target=main, args=(linkedin,))
        proc.start()
        INSTANCES[chat_id] = (linkedin, proc)


    def exit_proc(chat_id):
        logging.info("Завершение сеанса...")
        linkedin, _ = INSTANCES.get(chat_id, (None, None))
        q_kmd_in = linkedin.queue_kmd_input
        q_kmd_in.put("_kmd_chat_bot_exit")


    @bot.message_handler(commands=['start'])
    def start_command(message):
        bot_send_message(message.chat.id, 'Привет!')
        logging.info("Стартуем!")


    @bot.message_handler(content_types=['text'])
    def text_cmd(message):
        chat_id = message.chat.id
        linkedin, _ = INSTANCES.get(chat_id, (None, None))
        logging.info("Входящее сообщение: " + message.text)
        if message.text == "Начать поиск":
            if chat_id in INSTANCES:
                bot_send_message(chat_id, "Поиск уже идет, для завершения текущего поиска нажмите 'Завершить поиск'")
                pass
            elif chat_id not in INSTANCES:
                start(chat_id)
        elif message.text == "Завершить поиск" and chat_id in INSTANCES:
            exit_proc(chat_id)
        elif linkedin is not None:
            q = linkedin.queue_input
            q.put(message.text)
        else:
            pass


    app = Flask(__name__)


    @app.route('/health')
    def hello_world():
        return Response(status=200)


    print(__name__)

    threading.Thread(target=q_output_waiter).start()
    threading.Thread(target=q_output_kmd_waiter).start()
    threading.Thread(target=bot.polling, kwargs={'none_stop': True}).start()
    app.run(debug=True, host='0.0.0.0', port=80, use_reloader=False)
    # app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
