import logging

from aiohttp import web
from pymongo import MongoClient

from components.simple import register_commands
from .._common.configuration import MONGO_HOST, MONGO_PORT, MONGO_DB_NAME, QUEUE_SERVER
from modules.github.Module import GithubModule


async def github_callback(request):
    try:
        data = await request.json()
        headers = request.headers
        chat_hash = request.match_info['chat_hash']

        logging.debug((chat_hash, data, headers))

        headers = {param: headers.get(param, "") for param in ['X-GitHub-Event', 'X-GitHub-Delivery', 'X-Hub-Signature']}

        GithubHandler.run({"module": "github",
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


class GithubHandler:

    def __init__(self, web_app):
        self.WEB_APP = web_app

    def set_routes(self):
        self.WEB_APP.router.add_post('/github/{chat_hash}', github_callback)

    def register_commands(self, global_commands):
        register_commands('github', ['help', 'start', 'stop', 'delete'], global_commands)

    @staticmethod
    def run(params):
        MONGO_CLIENT = MongoClient(MONGO_HOST, MONGO_PORT)
        MONGO_DB = MONGO_CLIENT[MONGO_DB_NAME]
        github_module = GithubModule(QUEUE_SERVER, MONGO_DB)
        github_module.callback(params)