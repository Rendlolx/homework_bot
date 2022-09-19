import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot, TelegramError

from exceptions import (EmptyAPIResponseError, TelegramMessageError,
                        WrongAPIResponseCodeError)

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


def send_message(bot, message):
    """Отправка сообщения в чат."""
    logger.info(f'Отправляем сообщение в ТГ: {message}')

    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message
        )
    except TelegramError as error:
        raise TelegramMessageError(f'Ошибка отправки соообщения: {error}')
    else:
        logger.info('Сообщение отправлено!')


def get_api_answer(current_timestamp):
    """Запрос к Эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }

    try:
        logger.info(
            (
                'Начинаем подключение к {url}, с параметрами'
                ' headers = {headers}; params = {params}.'
            ).format(**request_params)
        )
        response = requests.get(**request_params)
    except WrongAPIResponseCodeError as error:
        raise ConnectionError(
            (
                'Во время подключения к {url} произошла'
                ' непредвиденная ошибка: {error}'
                ' headers = {headers}; params = {params};'
            ).format(error=error, **request_params)
        )

    if response.status_code != HTTPStatus.OK:
        raise WrongAPIResponseCodeError(
            'Ответ сервера не успешный:'
            f' params = {request_params};'
            f' http_code = {response.status_code};'
            f' reason = {response.reason}; content = {response.text}'
        )

    response = response.json()
    return response


def check_response(response):
    """Проверка ответа от сервера."""
    logger.info('Приступаю к проверке запроса по API')

    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API не словарь: response = {response}.'
        )
    homeworks = response['homeworks']

    if 'homeworks' not in response or 'current_date' not in response:
        raise EmptyAPIResponseError(
            'В ответе API отсутствуют необходимые ключи "homeworks" и/или'
            f' "current_date", response = {response}.'
        )

    if not isinstance(homeworks, list):
        raise KeyError(
            'В ответе, под ключом "homeworks" пришёл не список'
            f' response = {response}.'
        )

    return homeworks


def parse_status(homework):
    """Смена статуса работы."""
    print(homework)
    homework_name = homework['homework_name']
    if 'homework_name' not in homework:
        raise KeyError(
            'В домашней работе в ответе от API отсутствуют ключ'
            f' "homework_name" : homework = {homework}.'
        )

    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError(
            'В ответе от API пришел неизвестный статус работы,'
            f' status = {homework_status}.'
        )
    logger.debug(homework_status, 'Статус не изменился.')

    return (
        'Изменился статус проверки работы "{homework_name}". {verdict}'
    ).format(
        homework_name=homework_name,
        verdict=HOMEWORK_STATUSES[homework_status]
    )


def check_tokens():
    """Проверка переменных окружения."""
    try:
        if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
            return True
    except Exception as error:
        logger.exception(error, exc_info=True)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = (
            'Отсутствуют обязательнные переменные окружения: PRACTICUM_TOKEN,'
            ' TELEGRAM_TOKEN, TELEGRAM_CHAT_ID.'
            ' Программа остановлена.'
        )
        logger.critical(message)
        sys.exit(message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    current_report = {'name': '', 'output': ''}
    prev_report = current_report.copy()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            # response_list = check_response(response)
            # message = parse_status(response_list[0])
            current_timestamp = response.get('current_date', current_timestamp)
            new_homeworks = check_response(response)
            if new_homeworks:
                current_report['name'] = new_homeworks[0]['homework_name']
                current_report['output'] = parse_status(new_homeworks[0])
            else:
                current_report['output'] = (
                    f'За период от {current_timestamp} до настоящего момента'
                    ' домашних работ нет.'
                )
            if current_report != prev_report:
                send_message(bot, current_report['output'])
                prev_report = current_report.copy()
            else:
                logger.debug('В ответе нет новых статусов.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if current_report != prev_report:
                send_message(bot, current_report)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s : %(levelname)s : %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    main()
