import logging
import requests

from aiohttp import web

from components.simple import register_commands
from configuration.globalcfg import DB_SETTINGS
from modules._common.CommonHandler import CommonHandler
from modules.github.Module import GithubModule
from modules.github.authcfg import APP


class GithubHandler(CommonHandler):

    def __init__(self, web_app):
        super().__init__(web_app)

    def set_routes(self):
        self.WEB_APP.router.add_post('/github/{chat_hash}', self.github_callback)
        self.WEB_APP.router.add_get('/github/auth/{user_hash}', self.github_auth)

    def register_commands(self, global_commands):
        register_commands('github', ['help', 'start', 'stop', 'delete', 'auth'], global_commands)

    @staticmethod
    def get_description():
        return '/github — Модуль GitHub. Может присылать уведомления о новых коммитах, pull-реквестах.'

    async def run_telegram(self, params):
        module = GithubModule(GithubHandler.get_mongo(DB_SETTINGS['MONGO_HOST'],
                                                      DB_SETTINGS['MONGO_PORT'], DB_SETTINGS['MONGO_DB_NAME']),
                              GithubHandler.get_redis(DB_SETTINGS['REDIS_HOST'], DB_SETTINGS['REDIS_PORT']))
        await module.run_telegram(params)

    @staticmethod
    async def run_web(params):
        module = GithubModule(GithubHandler.get_mongo(DB_SETTINGS['MONGO_HOST'], DB_SETTINGS['MONGO_PORT'],
                                                      DB_SETTINGS['MONGO_DB_NAME']),
                              GithubHandler.get_redis(DB_SETTINGS['REDIS_HOST'], DB_SETTINGS['REDIS_PORT']))
        await module.run_web(params)

    @staticmethod
    async def github_callback(request):
        try:
            data = await request.json()
            headers = request.headers
            chat_hash = request.match_info['chat_hash']

            logging.debug((chat_hash, data, headers))

            headers = {param: headers.get(param, "") for param in
                       ['X-GitHub-Event', 'X-GitHub-Delivery', 'X-Hub-Signature']}

            await GithubHandler.run_web({"module": "github",
                                         "url": request.rel_url.path,
                                         "type": 1,  # Github message
                                         "data": {
                                             "chat_hash": chat_hash,
                                             "headers": headers,
                                             "payload": data
                                         }
                                         })
        except Exception as e:
            logging.warning("[github_callback] Message process error: [%s]" % e)

        return web.Response(text='OK')

    @staticmethod
    async def github_auth(request):
        code = request.rel_url.query.get("code", "")
        chat_hash = request.rel_url.query.get('state', '')

        user_hash = request.match_info['user_hash']

        response = requests.post('https://github.com/login/oauth/access_token',
                                 {'client_id': APP['CLIENT_ID'],
                                  'client_secret': APP['CLIENT_SECRET'],
                                  'code': code}, headers = {'Accept': 'application/json'})
        response = response.json()
        access_token = response.get('access_token')
        await GithubHandler.run_web({"module": "github",
                               "url": request.rel_url.path,
                               "type": 2,  # Github auth
                               "data": {
                                   "user_hash": user_hash,
                                   "chat_hash": chat_hash,
                                   "access_token": access_token
                               }
                               })

        return web.Response(text='После привязки аккаунта, вы получите сообщение в Telegram')