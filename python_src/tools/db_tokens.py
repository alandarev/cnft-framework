from classes.token import DBToken
from secrets import token_hex
from psycopg2.errors import RaiseException
from os import getenv
import json

from tools.misc import format_ada

MINTING_ADDRESS = getenv("MINTING_ADDRESS")
RESERVE_MINUTES = int(getenv("RESERVE_MINUTES"))

doggies_hash_map = None


def get_system_info(db, mc=None):
    if mc:
        system_info = mc.get('system_info')
        if system_info:
            return json.loads(system_info)
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(id) FROM doggies WHERE NOT is_sold")
        reserved_count, = cursor.fetchone()

        system_info = {'reserved': reserved_count}
        if mc:
            mc.set('system_info', json.dumps(system_info), 15)
        return system_info


def get_doggies_hash_map(db):
    global doggies_hash_map
    if not doggies_hash_map:
        with db.cursor() as c:
            c.execute("SELECT id, key FROM doggies;")
            doggies_hash_map = dict()
            for item in c.fetchall():
                doggies_hash_map[item[1]] = item[0]
    return doggies_hash_map

def reserve_whitelisted_token(db, token_id, key, price, tier):
    with db.cursor() as cursor:

        reserve_hash = token_hex(15)
        print(f"id={token_id}, key={key}, hash={reserve_hash}")
        try:
            cursor.execute(f"UPDATE doggies SET reserved_until = current_timestamp + INTERVAL '{RESERVE_MINUTES} min', reserve_hash = %s WHERE id = %s;", (reserve_hash, token_id))
            db.commit()
        except RaiseException:
            # Already reserved, shouldn't happen in this scenario
            db.rollback()
            return (False, {"error_code": 3, "error_message": "Failed at reserving, try again"})

        return (True, {"key":key, "price_lovelace":price, "price_ada": format_ada(price), "address":MINTING_ADDRESS, "timer": RESERVE_MINUTES * 60, "tier": int(tier)+1, 'reserve_hash': reserve_hash})


# Legacy method. We use RabbitMQ architecture to speed this all up
# Do not use. It is capped at around 300+ iops load. Which is still better than anything we saw ;-)
def reserve_random_token(db):
    with db.cursor() as cursor:

        # We don't combine "OR" logic in order to rely on INDEX
        cursor.execute("SELECT id, key, price FROM doggies WHERE reserved_until is NULL ORDER BY id ASC LIMIT 1;")
        if not cursor.rowcount:
            # Seek expired reservation tokens instead
            # TODO: change price when re-reserving to prevent two people competing for the same token
            cursor.execute("SELECT id, key, price FROM doggies WHERE (reserved_until < current_timestamp AND (NOT is_sold)) ORDER BY id ASC LIMIT 1;")

        if not cursor.rowcount:
            cursor.execute("SELECT COUNT(id) FROM doggies WHERE NOT is_sold")
            count, = cursor.fetchone()

            return (False, {"error_code": 2, "error_message": "All tokens are reserved and/or sold", "reserved": count})


        token_id, key, price = cursor.fetchone()

        reserve_hash = token_hex(15)
        print(f"id={token_id}, key={key}, hash={reserve_hash}")
        try:
            cursor.execute(f"UPDATE doggies SET reserved_until = current_timestamp + INTERVAL '{RESERVE_MINUTES} min', reserve_hash = %s WHERE id = %s;", (reserve_hash, token_id))
            db.commit()
        except RaiseException:
            # Already reserved, start over again
            db.rollback()
            return reserve_random_token(db)

        return (True, {"key":key, "price_lovelace":price, "price_ada": format_ada(price), "address":MINTING_ADDRESS, "timer": RESERVE_MINUTES * 60})


def get_token_by_minted_id(db, doggie_id = None):
    t = DBToken()
    assert doggie_id

    with db.cursor() as c:
        c.execute("SELECT id, doggie_metadata, doggie_image, is_visible FROM metadata_doggies WHERE doggie_id = %s",(doggie_id,))
        results = c.fetchone()
        if results:
            if not results[3]:
                # Not visible
                return False
            t.doggie_id = doggie_id
            t.doggie_metadata = results[1]
            t.doggie_image = results[2]
        else:
            return False

    return t

def load_db_token(db, key=None, doggie_id = None):
    t = DBToken()
    assert key or doggie_id

    with db.cursor() as c:
        if key:
            if not (key in get_doggies_hash_map(db)):
                return False
            doggie_id = get_doggies_hash_map(db)[key]
        c.execute("SELECT key, reserved_until, id, doggie_metadata, doggie_image FROM doggies WHERE id = %s",(doggie_id,))
        results = c.fetchone()
        if results:
            t.key = results[0]
            t.reserved_until = results[1]
            t.doggie_id = results[2]
            t.doggie_metadata = results[3]
            t.doggie_image = results[4]
        else:
            return False

    return t

def get_purchase_status(key, db_sync, db_tokens):
    assert key
    assert key in get_doggies_hash_map(db_tokens)

    doggie_id = get_doggies_hash_map(db_tokens)[key]

    with db_tokens.cursor() as c_tokens:
        c_tokens.execute("SELECT id, is_sold, price, EXTRACT (EPOCH FROM (reserved_until - current_timestamp)), tier, reserve_hash FROM doggies WHERE id = %s",(doggie_id,))
        doggie_id, is_sold, price, time_left, tier, reserve_hash = c_tokens.fetchone()

        if is_sold: return (True, {'price_lovelace': price, 'price_ada': format_ada(price), 'address': MINTING_ADDRESS, 'reserve_hash': reserve_hash})

        with db_sync.cursor() as c_sync:
            c_sync.execute("SELECT id FROM tx_out WHERE address = %s and value = %s", (MINTING_ADDRESS, price))

            if c_sync.rowcount:
                # Save is_sold as true
                c_tokens.execute("UPDATE doggies SET is_sold = TRUE WHERE id = %s", (doggie_id,))
                db_tokens.commit()
                return (True, {'price_lovelace': price, 'price_ada': format_ada(price), 'address': MINTING_ADDRESS, 'reserve_hash': reserve_hash})
            else:
                return (False, {'price_lovelace': price, 'price_ada': format_ada(price), 'timer': time_left, 'address': MINTING_ADDRESS, 'tier': int(tier) + 1, 'reserve_hash': reserve_hash})


def get_db_stats(db):
    with db.cursor() as c:
        c.execute("SELECT count(*) from doggies where is_sold = TRUE;")
        total_sold, = c.fetchone()
        c.execute("SELECT SUM(collected) from doggies where is_sent = TRUE;")
        total_collected, = c.fetchone()

        raised_funds = 0

        try:
            raised_funds = int(int(total_collected) / 2)
        except:
            pass

        raised_ada = format_ada(raised_funds)

        return {'sold': total_sold, 'raised_lovelace': raised_funds, 'raised_ada': raised_ada}


