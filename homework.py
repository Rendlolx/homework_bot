import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s : %(levelname)s : %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message
        )
        logger.info('Сообщение отправлено.')
    except Exception as error:
        logger.error(error, exc_info=True)


def get_api_answer(current_timestamp):
    """Запрос к Эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        logger.error(error, exc_info=True)

    logger.error('Непонятная ситуация')

    if response.status_code != HTTPStatus.OK:
        raise ValueError(f'Статус код не {HTTPStatus.OK}')

    response = response.json()
    return response


def check_response(response):
    """Проверка ответа от сервера."""
    current_timestamp = int(time.time())
    try:
        response = get_api_answer(current_timestamp)
    except Exception as error:
        logger.error(error, exc_info=True)

    if response['homeworks'] != list(response['homeworks']):
        raise TypeError('Данные не имеют тип list')

    response = response['homeworks']
    return response


def parse_status(homework):
    """Смена статуса работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logger.debug(homework_status, 'Статус не изменился.')
    return message


def check_tokens():
    """Проверка переменных окружения."""
    try:
        if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
            return True
    except Exception as error:
        logger.exception(error, exc_info=True)


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            response_list = check_response(response)
            if response_list is not False:
                message = parse_status(response_list)
                send_message(bot, message)
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            message = parse_status(response_list)
            send_message(bot, message)


if __name__ == '__main__':
    main()
