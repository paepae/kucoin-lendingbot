import json
from datetime import datetime
from random import shuffle

from flask import request
from flask.wrappers import Response
from google.cloud import firestore
from pytz import timezone

from bots.step import StepBot
from configuration import Configuration


def http_request(request: request):

    db = firestore.Client()
    config = get_configuration(db)

    json_params = request.get_json(silent=True)

    bot_params = {
        "should_execute": request.args.get("execute") == "1",
    }

    if json_params is not None:
        bot_params["get_lending_status"] = json_params.get("get_lending_status") == 1

    response = dict()
    if bot_params.get("get_lending_status"):
        response["timestamp"] = datetime.now(timezone("Asia/Bangkok")).strftime("%H:%M:%S%z")
        response["accounts"] = dict()

    shuffle(config.accounts)
    for account_config in config.accounts:
        if not account_config.active:
            continue

        bot = StepBot(account_config)
        bot_response = bot.execute(bot_params)
        if bot_response is not None:
            response["accounts"][account_config.name] = { "log": bot_response }

    if len(response) == 0:
        return "OK"

    return Response(json.dumps(response), mimetype="application/json")


def get_configuration(db) -> Configuration:
    config = Configuration(db)

    return config
