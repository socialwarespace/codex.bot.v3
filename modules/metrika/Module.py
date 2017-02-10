import logging
from components.simple import generate_hash
from modules.metrika.MetrikaAPI import MetrikaAPI
from .._common.functions import send_text, send_keyboard


class MetrikaModule:
    def __init__(self, db, redis, settings):
        self.db = db
        self.redis = redis
        self.settings = settings

    def run_telegram(self, params):
        try:
            payload = params['data']['payload']
            if not params['data']['inline']:
                self.make_answer(payload)
            else:
                self.process_inline_command(payload)

        except Exception as e:
            logging.error("Metrika module run_telegram error: {}".format(e))

    def run_web(self, params):
        try:
            access_token = params['data'].get("access_token", "")
            chat_id = params['data'].get("chat_id", "")
            metrika_api = MetrikaAPI(access_token, '', chat_id)

            logging.debug("run_web with params: {}".format(access_token, chat_id))

            if not self.db.metrika_tokens.find_one({'access_token': access_token}):
                self.db.metrika_tokens.insert_one({'id': generate_hash(12),
                                                   'chat_id': chat_id,
                                                   'access_token': access_token})

            self.metrika_telegram_start(chat_id)

        except Exception as e:
            logging.error("Metrika module run_web error: {}".format(e))

    def make_answer(self, message):
        try:
            command_prefix = message['text'].split(' ')[0]
            chat_id = message['chat']['id']

            if command_prefix.startswith("/help") or command_prefix.startswith("/metrika_help"):
                send_text(self.metrika_telegram_help(chat_id), chat_id)
                return

            if command_prefix.startswith("/start") or command_prefix.startswith("/metrika_start"):
                self.metrika_telegram_start(chat_id)
                return

            if command_prefix.startswith("/stop") or command_prefix.startswith("/metrika_stop"):
                self.metrika_telegram_stop(chat_id)
                return

            send_text('%%i_dont_know_such_a_command%%', chat_id)

        except Exception as e:
            logging.error("Error while Metrika make_answer: {}".format(e))

    def process_inline_command(self, message):
        try:
            command_prefix = message['text'].split(' ')[0]
            chat_id = message['chat']['id']

            if command_prefix.startswith("/add_counter") or command_prefix.startswith("/metrika_add_counter"):
                cache_id = message["text"].split("#")[-1]
                cached_data = self.redis.hgetall(cache_id)
                if cached_data:
                    self.metrika_telegram_add(chat_id, cached_data)

            if command_prefix.startswith("/del_counter") or command_prefix.startswith("/metrika_del_counter"):
                cache_id = message["text"].split("#")[-1]
                cached_data = self.redis.hgetall(cache_id)
                if cached_data:
                    self.metrika_telegram_del(chat_id, cached_data)

        except Exception as e:
            logging.error("Error while Metrika process_inline_command: {}".format(e))

    ### MESSAGES ###

    def metrika_telegram_help(self, chat_id):
        msg = "Этот модуль поможет вам следить за статистикой сайта. Возможности модуля: \n\n" \
              "- моментальное получение текущих значений счетчиков (DAU, просмотры, источники) за период (день, неделя, месяц)\n" \
              "- уведомление о достижении целей (например, бот сообщит о достижении показателя в 10k уникальных посетителей)"

        metrikas = list(self.db.metrika_counters.find({'chat_id': chat_id}))
        if not len(metrikas):
            msg += "\n\nВ данный момент модуль не активирован.\n\nДля настройки модуля, используйте команду /metrika_start"
        else:
            msg += "\n\nПодключенные сайты.\n\n"
            for metrika in metrikas:
                msg += "%s\n" % metrika['counter_name']
            msg += "\nДля отключения счетчика используйте команду /metrika_stop\n" \
                   "Подключить еще один сайт можно с помощью команды /metrika_start\n\n" \
                   "Меню модуля: /metrika_help"
        return msg

    def metrika_telegram_start(self, chat_id):
        msg = ""

        metrikas = list(self.db.metrika_tokens.find({'chat_id': chat_id}))
        if not len(metrikas):
            msg +=   "Для подключения счетчика, вам нужно авторизовать бота. " \
                     "Для этого, пройдите по ссылке и подтвердите доступ к счетчику. \n\n" \
                     "https://oauth.yandex.ru/authorize?response_type=code&client_id={}&state={}\n".format(
                        self.settings['ID'],
                        chat_id
                     )
            send_text(msg, chat_id)
        else:
            buttons = self.get_counters(metrikas[0], "start")
            if not len(buttons):
                send_text("У вас нет доступных счетчиков Яндекс Метрики.", chat_id)
            else:
                send_keyboard("Теперь выберите сайт, статистику которого хотите получать.\n",
                          buttons,
                          chat_id)

    def metrika_telegram_stop(self, chat_id):
        msg = ""

        metrikas = list(self.db.metrika_counters.find({'chat_id': chat_id}))
        if not len(metrikas):
            send_text("Подключенных счетчиков не найдено.", chat_id)
        else:
            send_keyboard("Выберите сайт, который хотите отключить.\n",
                          self.get_chat_counters(metrikas, chat_id),
                          chat_id)

    def metrika_telegram_add(self, chat_id, params):
        counter = self.db.metrika_counters.find_one({'chat_id': chat_id, 'counter_id': params['counter_id']})
        if counter:
            send_text("Счетчик <{}> уже прикреплен к данному чату.".format(params['name']), chat_id)
        else:
            self.db.metrika_counters.insert_one({
                'chat_id': chat_id,
                'counter_id': params['counter_id'],
                'counter_name': params['name'],
                'access_token': params['access_token']
            })
            send_text("Готово! Сайт <{}> успешно подключен.".format(params['name']), chat_id)
            self.metrika_telegram_help(chat_id)

    def metrika_telegram_del(self, chat_id, params):
        result = self.db.metrika_counters.delete_one({'chat_id': chat_id, 'counter_id': params['counter_id']})
        if result.deleted_count:
            send_text("Счетчик <{}> успешно откреплен от данного чата.".format(params['name']), chat_id)
        else:
            send_text("Счетчик <{}> к данному чату не подключен.".format(params['name']), chat_id)

    ### SUPPORT ###

    def get_counters(self, token, cmd):
        metrikaAPI = MetrikaAPI(token['access_token'], '', token['chat_id'])
        counters = metrikaAPI.get_counters()
        buttons = []
        buttons_row = []
        for counter in counters:
            cache_link = generate_hash(18)
            buttons_row.append(
                {
                    'text': counter["name"],
                    'callback_data': "/metrika_add_counter #{}#{}".format(cmd, cache_link)
                }
            )
            self.redis.hmset(cache_link, {'access_token': token['access_token'],
                                          'counter_id': counter['id'],
                                          'cmd': "start",
                                          'name': counter['name']})

            if len(buttons_row) == 2:
                buttons.append(buttons_row[:])
                buttons_row = []
        if len(buttons_row):
            buttons.append(buttons_row[:])
        return buttons

    def get_chat_counters(self, metrikas, chat_id):
        buttons = []
        buttons_row = []
        for counter in metrikas:
            cache_link = generate_hash(18)
            buttons_row.append({
                'text': counter['counter_name'],
                'callback_data': "/metrika_del_counter #{}#{}".format("stop", cache_link)
            })
            self.redis.hmset(cache_link, {'counter_id': counter['counter_id'],
                                          'chat_id': chat_id,
                                          'cmd': "stop",
                                          'name': counter['counter_name']})

            if len(buttons_row) == 2:
                buttons.append(buttons_row[:])
                buttons_row = []
        if len(buttons_row):
            buttons.append(buttons_row[:])
        return buttons