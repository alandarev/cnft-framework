from dotenv import load_dotenv
import atexit
import psycopg2
from os import getenv
from time import sleep

from cardano_tools import ShelleyTools

import constants
import tools.db_sync_tools as ds
from tools.cardano_cli_extra import make_policy, mint_and_send, send_back
from classes.token import token_constructor

json_loaded = None

load_dotenv()
LOVELACE_FOR_DROP = getenv('LOVELACE_FOR_DROP')
shelley = ShelleyTools(
            getenv("CARDANO_CLI"),
            getenv("CARDANO_NODE_SOCKET"),
            getenv("PRIVATE_FOLDER"),
            network=getenv("NETWORK_MAGIC"))

constants.initiate_constants(shelley)

db_sync = psycopg2.connect(getenv("CARDANO_DB_SYNC_POSTGRES_URL")) 

processed_utxos = []


def failsafe():
    # Do some basic asserts to ensure we're safe
    assert len(constants.STORAGE_ADDRESS) > 20

token_id = None
def get_next_token_id():
    global token_id
    if not token_id:
        token_id = int(constants.SIMPLE_ITERATOR.read_text())

    token_id = token_id + 1
    constants.SIMPLE_ITERATOR.write_text(str(token_id))

    return token_id

def get_next_token_info():
    metadata = constants.SIMPLE_METADATA

    token_id = get_next_token_id()

    id_formatted = "{:04d}".format(token_id)
    metadata_iterated = metadata.replace("0000", id_formatted)

    return token_id, metadata_iterated

def worker_heartbeat():
    global db_sync
    while True:
        # Ensure DB Sync is online
        if db_sync.closed:
            print("Reconnecting to DB Sync...")
            db_sync = psycopg2.connect(getenv("CARDANO_DB_SYNC_POSTGRES_URL")) 
        for utxo in shelley.get_utxos(constants.MINTING_ADDRESS):
            if utxo['TxHash'] in processed_utxos:
                print(f"Skipping: {utxo['TxHash']} - already processed")
                continue

            tx_hash = utxo['TxHash']
            tx_ix = utxo['TxIx']
            tx_amount = utxo['Lovelace']


            try:
                tx_id = ds.get_tx_id(db_sync, tx_hash)
            except:
                # The TX is not in database yet. DB Sync might be behind. Need to wait
                print(f"Skipping: {utxo['TxHash']} - No record in the DB Sync")
                continue
            processed_utxos.append(utxo['TxHash'])

            sender_addr = ds.get_sender_address(db_sync, tx_id)
            # Find the matching doggie if any
            if tx_amount != LOVELACE_FOR_DROP:
                print(f"Processing transaction {tx_hash}#{tx_ix}.\nWrong value. Returning money to {sender_addr}")
                send_back(shelley, utxo, sender_addr)

            else:
                token_id, metadata = get_next_token_info()
                t = token_constructor(token_id, metadata)

                collected, trans_results = mint_and_send(
                                shelley,
                                utxo,
                                sender_addr,
                                constants.STORAGE_ADDRESS,
                                t,
                                wallet_key=constants.WALLET_SKEY
                             )

                print(f"Processed transaction {tx_hash}#{tx_ix}.\nMinting {t.name} to {sender_addr}.\nAnd {collected} to {constants.STORAGE_ADDRESS}")

            sleep(0.02)
        print("Heartbeat beep")
        try:
            db_sync.rollback()
        except:
            # Probably lost connection, do nothing
            pass
        sleep(8)


def onexit():
    try:
        db_sync.close()
    except e:
        pass
    print("Gracefully closed connections")


atexit.register(onexit)

failsafe()

