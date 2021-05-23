
def get_tx_id(db_sync_conn,tx_hash):
    full_hash = r"\x" + tx_hash

    with db_sync_conn.cursor() as c:
        c.execute("SELECT id from tx where hash = %s", (full_hash,))

        return c.fetchone()[0]

def get_sender_address(db_sync_conn,tx_id):
     with db_sync_conn.cursor() as c:

        c.execute("SELECT tx_out_id, tx_out_index from tx_in where tx_in_id = %s", (tx_id,))
        tx_out_id, tx_out_index = c.fetchone()

        c.execute("SELECT address FROM tx_out WHERE tx_id = %s AND index = %s", (tx_out_id, tx_out_index))
        address = c.fetchone()[0]

        return address

