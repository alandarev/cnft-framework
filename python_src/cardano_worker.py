from dotenv import load_dotenv
import atexit
import psycopg2
from os import getenv
from time import sleep

from cardano_tools import ShelleyTools

import constants
import tools.db_sync_tools as ds
from tools.cardano_cli_extra import make_policy, mint_and_send, send_back
from classes.token import doggie_token_constructor


load_dotenv()
shelley = ShelleyTools(
            getenv("CARDANO_CLI"),
            getenv("CARDANO_NODE_SOCKET"),
            getenv("PRIVATE_FOLDER"),
            network=getenv("NETWORK_MAGIC"))

db_sync = psycopg2.connect(getenv("CARDANO_DB_SYNC_POSTGRES_URL"))
db_tokens = psycopg2.connect(getenv("TOKENS_DB_URL"))
constants.initiate_constants(shelley)


processed_utxos = []


def failsafe():
    # Do some basic asserts to ensure we're safe
    assert len(constants.STORAGE_ADDRESS) > 20


def create_keys():
    # Create the keys, address, minting policy
    # !This will override existing keys!
    shelley.make_address(constants.MINTING_WALLET)
    make_policy(shelley, constants.MINTING_POLICY)


def worker_heartbeat():
    while True:
        for utxo in shelley.get_utxos(constants.MINTING_ADDRESS):
            if utxo['TxHash'] in processed_utxos:
                print(f"Skipping: {utxo['TxHash']} - already processed")
                continue

            tx_hash = utxo['TxHash']
            tx_ix = utxo['TxIx']
            tx_amount = utxo['Lovelace']

            tx_id = None
            try:
                tx_id = ds.get_tx_id(db_sync, tx_hash)
            except:
                # The TX is not in database yet. DB Sync might be behind. Need to wait
                print(f"Skipping: {utxo['TxHash']} - No record in the DB Sync")
                continue
            processed_utxos.append(utxo['TxHash'])

            sender_addr = ds.get_sender_address(db_sync, tx_id)

            # Find the matching doggie if any
            with db_tokens.cursor() as c:
                c.execute("SELECT id, doggie_metadata, doggie_id FROM doggies WHERE (price = %s) AND (is_sent = FALSE)", (tx_amount,))
                if not c.rowcount:
                    # No doggie, return money
                    # TODO: finish

                    print(f"Processing transaction {tx_hash}#{tx_ix}.\nWrong value. Returning money to {sender_addr}")
                    send_back(shelley, utxo, sender_addr)
                else:
                    idx, doggie_metadata, doggie_id = c.fetchone()
                    t = doggie_token_constructor(doggie_id, doggie_metadata)

                    collected, trans_results = mint_and_send(
                                    shelley,
                                    utxo,
                                    sender_addr,
                                    constants.STORAGE_ADDRESS,
                                    t,
                                    wallet_key=constants.WALLET_SKEY
                                 )

                    print(f"COLLECTED {collected}. For Token ID = {idx}")

                    c.execute("UPDATE doggies SET is_sent = TRUE, is_sold = TRUE, collected = %s WHERE id = %s", (collected, idx))
                    db_tokens.commit()
                    print(f"Processed transaction {tx_hash}#{tx_ix}.\nMinting {t.name} to {sender_addr}.\nThe rest to {constants.STORAGE_ADDRESS}")

            sleep(0.02)
        print("Heartbeat beep")
        sleep(8)
        db_sync.rollback()
        db_tokens.rollback()


def onexit():
    try:
        db_sync.close()
    except e:
        pass
    print("Gracefully closed connections")


atexit.register(onexit)

failsafe()

