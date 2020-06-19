# common
import datetime
from datetime import timedelta
import requests
import re
from collections import defaultdict
# vk
import vk_api
from vk_api import VkUpload
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
# google
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

session = requests.Session()
vk_session = vk_api.VkApi(
    token='TOKEN')
vk = vk_session.get_api()
upload = VkUpload(vk_session)  # Для загрузки изображений
longpoll = VkLongPoll(vk_session)
months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября',
          'ноября', 'декабря']
days_of_week = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
data_from_user = defaultdict(lambda: {})


class Hall:
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self, name, price, calendar_id):
        self.name = name
        self.price = price
        self.calendar_id = calendar_id

    def calendar(self, command, day_argument='01 июня (Пн)', user_id=1):
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)

        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId=self.calendar_id,
                                              timeMin=now,
                                              singleEvents=True, orderBy='startTime').execute()

        events = events_result.get('items', [])
        open_hours = [i for i in range(10, 23)]
        busy_time = []

        wanted_date = datetime.date(2020, int(months.index(day_argument.split()[1]) + 1),
                                    int(day_argument.split()[0])).isoformat()

        for event in events:
            date = event['start'].get('dateTime')[0:10]
            start_time = event['start'].get('dateTime')[11:13]
            end_time = event['end'].get('dateTime')[11:13]
            if date == wanted_date:
                for i in range(int(start_time), int(end_time)):
                    busy_time.append(i)
                    # print(date, start_time, end_time, event['summary'])

        if command == 'show':
            # находим свободные часы: убираем значения из времени работы, которые присутствуют в занятом времени
            update_data_from_user(user_id, 'free_time', set(open_hours).difference(busy_time))

        if command == 'add':
            update_data_from_user(user_id, 'start_time', datetime.datetime(2020,
                                           int(months.index(get_data_from_user(user_id)["selected_day"].split()[1]) + 1),
                                           int(get_data_from_user(user_id)["selected_day"].split()[0]),
                                           int(get_data_from_user(user_id)["selected_time"][0:2]), 0, 0))
            update_data_from_user(user_id, 'end_time', get_data_from_user(user_id)['start_time'] + timedelta(hours=get_data_from_user(user_id)["selected_hours_for_reserve"]))

            # готовим финальный текст на выдачу
            final_info = ('Успешно забронировано:\n'
                            f'Зал: {get_data_from_user(user_id)["selected_hall"]}\n'
                            f'Дата: {get_data_from_user(user_id)["selected_day"]}\n'
                            f'Время: {get_data_from_user(user_id)["start_time"].strftime("%H:%M")} '
                            f'- {get_data_from_user(user_id)["end_time"].strftime("%H:%M")}\n'
                            f'Стоимость: {get_data_from_user(user_id)["final_price"]} рублей\n\n'
                            )

            # проверка на то что кто-то в этот момент уже забронировал это время
            for i in range(int(get_data_from_user(user_id)["start_time"].strftime("%H")),
                           int(get_data_from_user(user_id)["end_time"].strftime("%H")) + 1):
                if i in busy_time:
                    update_data_from_user(user_id, 'info_about_reserve', 'К сожалению, это время кто-то только что '
                                                                         'занял, пожалуйста, оформите новую бронь.')
                    break

                else:
                    event = {
                        'summary': get_data_from_user(user_id)["user_name"],
                        # 'location': '800 Howard St., San Francisco, CA 94103',
                        'description': 'Забронировано с помощью бота вконтакте.',
                        'start': {
                            'dateTime': get_data_from_user(user_id)["start_time"].strftime("%Y-%m-%dT%H:%M:%S"),
                            'timeZone': 'Europe/Moscow',
                        },
                        'end': {
                            'dateTime': get_data_from_user(user_id)["end_time"].strftime("%Y-%m-%dT%H:%M:%S"),
                            'timeZone': 'Europe/Moscow',
                        },
                    }

                    event = service.events().insert(calendarId=self.calendar_id, body=event).execute()
                    print('success add')
                    update_data_from_user(user_id, 'info_about_reserve', final_info)
                    break


paradniy_hall = Hall('Парадный', 800, 'calendar_id')
grand_hall = Hall('Гранд', 1000, 'calendar_id')
bonapart_hall = Hall('Бон-Апарт', 800, 'calendar_id')
passage_hall = Hall('Пассаж', 700, 'calendar_id')


def keyboards(keyboard_name, user_id=1):
    free_time_keyboard = VkKeyboard(one_time=True)
    free_time_keyboard.add_button('Свободное время', color=VkKeyboardColor.POSITIVE)

    hall_keyboard = VkKeyboard(one_time=True)
    hall_keyboard.add_button(paradniy_hall.name, color=VkKeyboardColor.DEFAULT)
    hall_keyboard.add_button(grand_hall.name, color=VkKeyboardColor.DEFAULT)
    hall_keyboard.add_line()
    hall_keyboard.add_button(bonapart_hall.name, color=VkKeyboardColor.DEFAULT)
    hall_keyboard.add_button(passage_hall.name, color=VkKeyboardColor.DEFAULT)

    week_choose_keyboard = VkKeyboard(one_time=True)
    week_choose_keyboard.add_button('Эта неделя', color=VkKeyboardColor.DEFAULT)
    week_choose_keyboard.add_button('Следующая неделя', color=VkKeyboardColor.DEFAULT)
    week_choose_keyboard.add_line()
    week_choose_keyboard.add_button('Более поздняя дата', color=VkKeyboardColor.DEFAULT)

    reserve_keyboard = VkKeyboard(inline=True)
    reserve_keyboard.add_button('Забронировать', color=VkKeyboardColor.DEFAULT)

    day_choose_keyboard = VkKeyboard(one_time=False)
    day_button = weeks_and_days('first_week')
    if keyboard_name == 'day_choose_keyboard_second':
        day_button = weeks_and_days('second_week')
    day_choose_keyboard.add_button(day_button[0], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_button(day_button[1], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_line()
    day_choose_keyboard.add_button(day_button[2], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_button(day_button[3], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_line()
    day_choose_keyboard.add_button(day_button[4], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_button(day_button[5], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_line()
    day_choose_keyboard.add_button(day_button[6], color=VkKeyboardColor.DEFAULT)
    day_choose_keyboard.add_button('Другая дата', color=VkKeyboardColor.DEFAULT)

    if keyboard_name == 'free_time_keyboard':
        return free_time_keyboard.get_keyboard()

    elif keyboard_name == 'pay_keyboard':
        pay_keyboard = VkKeyboard(one_time=True)
        pay_keyboard.add_button('Сделать перевод', color=VkKeyboardColor.POSITIVE)
        pay_keyboard.add_line()
        pay_keyboard.add_vkpay_button(
            # hash=f"action=pay-to-user&amount={str(get_data_from_user(user_id)['final_price'] / 2)}
            # &description={get_data_from_user(user_id)['user_name']}&user_id=")
            hash=f"action=pay-to-user&amount=2&description={get_data_from_user(user_id)['user_name']}&user_id=ID")
        return pay_keyboard.get_keyboard()

    elif keyboard_name == 'reserve_keyboard':
        return reserve_keyboard.get_keyboard()

    elif keyboard_name == 'hall_keyboard':
        return hall_keyboard.get_keyboard()

    elif keyboard_name == 'week_choose_keyboard':
        return week_choose_keyboard.get_keyboard()

    elif keyboard_name == 'time_choose_keyboard':
        time_choose_keyboard = VkKeyboard(one_time=True)
        time_button = [str(i) + ':00' for i in get_data_from_user(user_id)['free_time']]
        n = 0
        for i in time_button:
            try:
                time_choose_keyboard.add_button(time_button[n], color=VkKeyboardColor.DEFAULT)
                n += 1
            except ValueError:
                time_choose_keyboard.add_line()
                time_choose_keyboard.add_button(time_button[n], color=VkKeyboardColor.DEFAULT)
                n += 1

        time_choose_keyboard.add_line()
        time_choose_keyboard.add_button('Изменить дату', color=VkKeyboardColor.DEFAULT)

        return time_choose_keyboard.get_keyboard()

    elif keyboard_name == 'reserve_hours_keyboard':
        reserve_hours_keyboard = VkKeyboard(one_time=True)
        hour_button = [i for i in range(1, hours_for_reserve(user_id) + 1)]
        n = 0
        for i in hour_button:
            try:
                reserve_hours_keyboard.add_button(str(hour_button[n]) + ' ч.', color=VkKeyboardColor.DEFAULT)
                n += 1
            except ValueError:
                reserve_hours_keyboard.add_line()
                reserve_hours_keyboard.add_button(str(hour_button[n]) + ' ч.', color=VkKeyboardColor.DEFAULT)
                n += 1

        reserve_hours_keyboard.add_line()
        reserve_hours_keyboard.add_button('Изменить дату', color=VkKeyboardColor.DEFAULT)

        return reserve_hours_keyboard.get_keyboard()

    elif keyboard_name == 'day_choose_keyboard_first' or 'day_choose_keyboard_second':
        return day_choose_keyboard.get_keyboard()


def weeks_and_days(week):
    today = datetime.date.today()
    first_day_of_second_week = today + timedelta(days=7)
    first_week = []
    second_week = []

    current_month = ''
    n = 0

    while current_month == '':
        if int(today.strftime('%m')) == n + 1:
            current_month = months[n]
        n += 1

    while len(first_week) != 7:
        first_week.append(today.strftime(f'%d {current_month} ({days_of_week[today.weekday()]})'))
        today += timedelta(days=1)
        # в случае, если в течении недели сменится месяц происходит такая проверочка-заменочка
        if int(today.strftime('%d')) < int((today - timedelta(days=1)).strftime('%d')):
            current_month += 1

    while len(second_week) != 7:
        second_week.append(first_day_of_second_week.strftime(
            f'%d {current_month} ({days_of_week[first_day_of_second_week.weekday()]})'))
        first_day_of_second_week += timedelta(days=1)
        # в случае, если в течении недели сменится месяц происходит такая проверочка-заменочка
        if int(today.strftime('%d')) < int((today - timedelta(days=1)).strftime('%d')):
            current_month += 1

    if week == 'first_week':
        return first_week
    elif week == 'second_week':
        return second_week


def hours_for_reserve(user_id):
    # индекс запрашиваемого пользователем часа
    selected_time = list(get_data_from_user(user_id)['selected_time'])
    start_hour_index = list(get_data_from_user(user_id)['free_time']).index(int(get_data_from_user(user_id)['selected_time'][0:2]))
    greater_then_selected_time = [time for time in list(get_data_from_user(user_id)['free_time'])
                                  if time >= list(get_data_from_user(user_id)['free_time'])[start_hour_index]]
    n = 0
    try:
        for i in greater_then_selected_time:
            if greater_then_selected_time[n + 1] - greater_then_selected_time[n] > 1:
                return n + 1
            else:
                n += 1
    # в случае если все последующие часы в этот день свободны
    except IndexError:
        return len(greater_then_selected_time)


def update_data_from_user(user_id, key, value):
    data_from_user[user_id][key] = value


def get_data_from_user(user_id):
    return data_from_user[user_id]


def check_none_keys(user_id, key):
    if get_data_from_user(user_id).get(key) is None:
        update_data_from_user(user_id, key, '')


def main():
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text or event.attachments:
            user_info = vk.users.get(user_ids=event.user_id)

            print('id{}: "{}"'.format(event.user_id, event.text), end=' ')

            selected = ['selected_hall', 'selected_time', 'selected_hours_for_reserve', 'selected_day', 'free_time',
                        'successful_reserve']
            for s in selected:
                check_none_keys(event.user_id, s)

            if event.text.lower() in ['свободное время', 'стоп']:

                update_data_from_user(event.user_id, 'user_name',
                                      f"{user_info[0]['first_name']} {user_info[0]['last_name']} "
                                      f"vk.com/gim1111111?sel={user_info[0]['id']}")

                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('hall_keyboard'),
                    message=('Я могу показать вам свободное время в залах, а так же поставить бронь. Для этого '
                             'просто следуйте моим указаниям и нажимайте на кнопки. Если в какой-то момент вы захотите '
                             'вернуться к началу, то просто напишите мне "Стоп".\n\n'
                             'Сейчас выберите зал для бронирования.')
                )
                print('ok')

            if event.text in [passage_hall.name, paradniy_hall.name, bonapart_hall.name, grand_hall.name]:
                update_data_from_user(event.user_id, 'selected_hall', event.text)
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('week_choose_keyboard'),
                    message='Когда вы хотели бы забронировать зал?'
                )
                print('ok')

            if event.text.lower() in ['другая дата', 'изменить дату']:
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('week_choose_keyboard'),
                    message='Когда вы хотели бы забронировать зал?'
                )
                print('ok')

            if event.text.lower() == 'эта неделя':
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('day_choose_keyboard_first'),
                    message='Выберите день для бронирования'
                )
                print('ok')

            if event.text.lower() == 'следующая неделя':
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('day_choose_keyboard_second'),
                    message='Выберите день для бронирования'
                )
                print('ok')

            if event.text.lower() == 'более поздняя дата':
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    # keyboard=keyboards('day_choose_keyboard_second'),
                    message='Напишите желаемую дату в формате "03 декабря"'
                )
                print('ok')

            # в случае, если пользователь выбрал какую-то дату запускается проверка в календаре по этой дате
            for i in months:
                if event.text.find(i) != -1:

                    update_data_from_user(event.user_id, 'selected_day', event.text)

                    # проводим поиск свободного времени
                    if get_data_from_user(event.user_id)['selected_hall'] == grand_hall.name:
                        grand_hall.calendar('show', get_data_from_user(event.user_id)['selected_day'], event.user_id)
                    elif get_data_from_user(event.user_id)['selected_hall'] == paradniy_hall.name:
                        paradniy_hall.calendar('show', get_data_from_user(event.user_id)['selected_day'], event.user_id)
                    elif get_data_from_user(event.user_id)['selected_hall'] == bonapart_hall.name:
                        bonapart_hall.calendar('show', get_data_from_user(event.user_id)['selected_day'], event.user_id)
                    elif get_data_from_user(event.user_id)['selected_hall'] == passage_hall.name:
                        passage_hall.calendar('show', get_data_from_user(event.user_id)['selected_day'], event.user_id)

                    # проверяем, не занято ли всё время в этот день
                    if get_data_from_user(event.user_id)['free_time']:
                        vk.messages.send(
                            user_id=event.user_id,
                            random_id=get_random_id(),
                            keyboard=keyboards('reserve_keyboard'),
                            message=event.text + ': ' + ', '.join(
                                [str(i) + ':00' for i in get_data_from_user(event.user_id)['free_time']])
                        )

                    else:
                        vk.messages.send(
                            user_id=event.user_id,
                            random_id=get_random_id(),
                            message='Всё время на этот день занято. Выберите другую дату.'
                        )

            if event.text.lower() == 'забронировать':
                if get_data_from_user(event.user_id)['free_time'] == '':
                    vk.messages.send(
                        user_id=event.user_id,
                        random_id=get_random_id(),
                        keyboard=keyboards('free_time_keyboard', event.user_id),
                        message='Для того, чтобы поставить новую бронь нажмите "Свободное время"'
                    )
                    print('ok')

                else:
                    vk.messages.send(
                        user_id=event.user_id,
                        random_id=get_random_id(),
                        keyboard=keyboards('time_choose_keyboard', event.user_id),
                        message='На какое время вы хотели бы забронировать зал?'
                    )
                    print('ok')

            if event.text in [str(i) + ':00' for i in get_data_from_user(event.user_id)['free_time']]:
                update_data_from_user(event.user_id, 'selected_time', event.text)
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('reserve_hours_keyboard', event.user_id),
                    message=f'На сколько часов вы хотите забронировать зал?'
                )

            if event.text in [str(i) + ' ч.' for i in range(1, 14)]:
                # находим число в присланном сообщении
                update_data_from_user(event.user_id, 'selected_hours_for_reserve',
                                      int(re.findall('(\d+)', event.text)[0]))

                if get_data_from_user(event.user_id)['selected_hall'] == grand_hall.name:
                    update_data_from_user(event.user_id, 'final_price', grand_hall.price * get_data_from_user(event.user_id)['selected_hours_for_reserve'])
                    grand_hall.calendar('add', get_data_from_user(event.user_id)['selected_day'], event.user_id)
                elif get_data_from_user(event.user_id)['selected_hall'] == paradniy_hall.name:
                    update_data_from_user(event.user_id, 'final_price', paradniy_hall.price * get_data_from_user(event.user_id)['selected_hours_for_reserve'])
                    paradniy_hall.calendar('add', get_data_from_user(event.user_id)['selected_day'], event.user_id)
                elif get_data_from_user(event.user_id)['selected_hall'] == bonapart_hall.name:
                    update_data_from_user(event.user_id, 'final_price', bonapart_hall.price * get_data_from_user(event.user_id)['selected_hours_for_reserve'])
                    bonapart_hall.calendar('add', get_data_from_user(event.user_id)['selected_day'], event.user_id)
                elif get_data_from_user(event.user_id)['selected_hall'] == passage_hall.name:
                    update_data_from_user(event.user_id, 'final_price', passage_hall.price * get_data_from_user(event.user_id)['selected_hours_for_reserve'])
                    passage_hall.calendar('add', get_data_from_user(event.user_id)['selected_day'], event.user_id)

                with open('/Users/Mishanya/Documents/python/HelloWorld/calendar/reserve_info.txt', 'r') as reserve_info:
                    text = reserve_info.read()

                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    keyboard=keyboards('pay_keyboard', event.user_id),
                    message=get_data_from_user(event.user_id)['info_about_reserve'] + text
                )

                print(data_from_user.get(event.user_id))
                data_from_user.pop(event.user_id)
                # update_data_from_user(event.user_id, 'successful_reserve', True)

            if event.text.lower() == 'сделать перевод':
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    # keyboard=keyboards('reserve_hours_keyboard', event.user_id),
                    message='Для внесения предоплаты перейдите по ссылке ниже и введите данные: vk.cc/00000\n\n'
                            'После оплаты обязательно пришлите ответным сообщением скриншот вашего платежа.'
                )
                print('ok')

            # if event.attachments:
            #     # проверяем, поставил ли он до этого бронь
            #     if get_data_from_user(event.user_id)['successful_reserve']:
            #         vk.messages.send(
            #             user_id=event.user_id,
            #             random_id=get_random_id(),
            #             # keyboard=keyboards('reserve_hours_keyboard', event.user_id),
            #             message='Пересылаю администратору для проверки. '
            #                     'В ближайшее время вам ответят с подтверждением бронирования.'
            #         )
            #
            #         vk.messages.send(
            #             user_id=240568595,
            #             random_id=get_random_id(),
            #             message=f'{user_info[0]["first_name"]} {user_info[0]["last_name"]} произвёл предоплату, '
            #                     f'нужно проверить:\nvk.com/gim25602033?sel={user_info[0]["id"]}'
            #         )
            #
            #     data_from_user.pop(event.user_id)


if __name__ == '__main__':
    main()