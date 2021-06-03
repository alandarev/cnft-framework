import falcon
from os import getenv
from dotenv import load_dotenv
load_dotenv()
import psycopg2
import pylibmc
import datetime
#import falcon.asgi
import falcon_jsonify
from falcon_caching import Cache
from time import sleep
import json
from urllib import request

from tools.db_tokens import get_system_info, reserve_whitelisted_token, get_purchase_status, load_db_token, get_db_stats, get_token_by_minted_id
from tools.queue import get_channel

cache = Cache(
        config={
            'CACHE_TYPE': 'memcached',
            'CACHE_EVICTION_STRATEGY': 'time-based',
            'CACHE_MEMCACHED_SERVERS': ["127.0.0.1:11211",],
            'CACHE_CONTENT_TYPE_JSON_ONLY': True,
        })


db_sync = None
db_tokens = None
mc = None

LIMIT_RESERVES_SECONDS=int(getenv("LIMIT_RESERVES_SECONDS"))

def is_db_valid(db):
    if not db:
        return False
    return True

class LoadDBInterface:
    def process_request(self, req, resp):
        global db_sync
        global db_tokens
        global mc

        if not is_db_valid(db_sync):
            print("Connecting to DB_SYNC")
            db_sync = psycopg2.connect(getenv("CARDANO_DB_SYNC_POSTGRES_URL"))
        if not is_db_valid(db_tokens):
            if not getenv("TOKENS_DB_URL"):
                print("Skipping connection to DB Tokens. No URL set")
            else:
                print("Connecting to DB TOKENS")
                db_tokens = psycopg2.connect(getenv("TOKENS_DB_URL"))
        if not mc:
            print("Connecting to memcache")
            mc = pylibmc.Client(["127.0.0.1"])

    def process_resource(self, req, resp, resource, params):
        pass
    def process_response(self, req, resp, resource, req_succeeded):
        # Erase the DB state
        db_tokens.rollback()
        db_sync.rollback()
        pass


class ReserveToken(object):
    def on_get(self, req, resp):
        limiter = "lim_" + str(req.remote_addr)
        time_limit = mc.get(limiter)

        # Temporarily disabled Limiter
        # if False:
        if time_limit and (time_limit > datetime.datetime.now()):
            seconds = (time_limit - datetime.datetime.now()).seconds
            resp.json = {'status': False, 'payload': {'error_code': 1, 'error_message': f'Please wait {seconds} seconds before reserving a new token', 'timer': seconds}}

        else:
            channel = get_channel()
            method_frame, header_frame, token_data = channel.basic_get('doggies', auto_ack=True)

            if token_data:
                token_id, token_key, token_price, token_tier, _ = token_data.decode('utf-8').split(',')
                reserve_results = reserve_whitelisted_token(db_tokens, int(token_id), token_key, token_price, token_tier)

                mc.set(limiter, datetime.datetime.now() + datetime.timedelta(seconds=LIMIT_RESERVES_SECONDS))

                resp.json = {'status': reserve_results[0], 'payload': reserve_results[1]}
            else:
                system_info = get_system_info(db_tokens, mc)
                system_info.update({"error_code": 2, "error_message": "All tokens are reserved and/or sold"})
                resp.json = {'status': False, 'payload': system_info}

class DoggieInfo(object):
    @cache.cached(timeout=120)
    def on_get(self, req, resp, doggie_id):
        doggie_info = None
        try:
            doggie_info = get_token_by_minted_id(db_tokens, doggie_id)
        except Exception as e:
            # Not authorized
            resp.json = {'status': False,
                         'payload': {'error': 3, 'error_message': 'Invalid ID'}}
            return

        if not doggie_info:
            resp.json = {'status': False,
                         'payload': {'error': 3, 'error_message': 'Invalid ID'}}
            return

        resp.json = {'status': True, 'metadata': doggie_info.doggie_metadata }

class GetPurchaseStatus(object):
    @cache.cached(timeout=9)
    def on_get(self, req, resp, key, reserve_hash):
        try:
            status = get_purchase_status(key, db_sync, db_tokens)
        except Exception:
            # Not authorized
            resp.json = {'status': False,
                         'payload': {'error': 3, 'error_message': 'Reserve Hash does not match. Not Authorized'}}
            return


        if (not reserve_hash) or (reserve_hash != status[1]['reserve_hash']):
            # Not authorized
            resp.json = {'status': False,
                         'payload': {'error': 3, 'error_message': 'Reserve Hash does not match. Not Authorized'}}
            return

        if status[0] == True:
            # We've got a lucky doggy owner
            # Get the doggie data
            t = load_db_token(db_tokens, key)
            resp.json = {'status': status[0],
                         'payload': status[1],
                         'metadata': t.doggie_metadata
                        }
        else:
            resp.json = {'status': status[0],
                         'payload': status[1],
                        }


class GenericInfo(object):
    @cache.cached(timeout=32) # 30 sec is coingecko cache, so it makes sense to have higher
    def on_get(self, req, resp):
        db_stats = get_db_stats(db_tokens)
        cardano_price = None
        try:
            response = request.urlopen("https://api.coingecko.com/api/v3/simple/price?ids=cardano&vs_currencies=usd", timeout=10)
            cardano_price = json.loads(response.read())
        except:
            cardano_price = {'error': 'coingecko did not respond'}

        resp.json = {'stats': db_stats, 'cardano_info': cardano_price}


middleware = [
        LoadDBInterface(),
        cache.middleware,
        falcon_jsonify.Middleware(help_messages=True),
]

app = falcon.App(middleware=middleware, cors_enable=True)

app.add_route('/reserve', ReserveToken())
app.add_route('/status/{key}/{reserve_hash}', GetPurchaseStatus())
app.add_route('/info', GenericInfo())
app.add_route('/doggie/{doggie_id}', DoggieInfo())

application = app
