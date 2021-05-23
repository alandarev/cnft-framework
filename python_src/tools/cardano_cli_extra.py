from pathlib import Path
from uuid import uuid4
from datetime import datetime
import json

import constants

def make_policy(shelley, name):

    print("MAKE POLICY")
    folder = shelley.working_dir

    policy_folder = folder / "policy"
    policy_folder.mkdir(parents=True, exist_ok=True)

    policy_vkey = policy_folder / (name + ".vkey")
    policy_skey = policy_folder / (name + ".skey")
    policy_script = policy_folder / (name + ".script")
    policy_hash = policy_folder / (name + ".hash")

    shelley.run_cli(
            f"{shelley.cli} address key-gen "
            f"--verification-key-file {policy_vkey} "
            f"--signing-key-file {policy_skey}"
            )

    policy_key_hash = shelley.run_cli(f"{shelley.cli} address key-hash --payment-verification-key-file {policy_vkey}").stdout

    policy_script_content = (
            '{\n'
            f'"keyHash": "{policy_key_hash}",\n'
            f'"type": "sig"\n'
            '}'
            )
    with open(f"{policy_script}", "w") as file_handle:
        file_handle.write(policy_script_content)

    policy_script_hash = shelley.run_cli(f"{shelley.cli} transaction policyid --script-file {policy_script}").stdout

    with open(f"{policy_hash}", "w") as file_handle:
        file_handle.write(policy_script_hash)

def sign_transaction(shelley, tx_file, skeys, script=None) -> str:
    # Fixes sign transaction writing the result file in a wrong folder
    signing_key_args = ""
    for key_path in skeys:
        signing_key_args += f"--signing-key-file {key_path} "

    # Multi-signature Script
    script_str = ""
    if script is not None:
        script_str = f" --script-file {script} "

    # Sign the transaction with the signing key
    tx_signed_file = Path(tx_file).with_suffix('.signed')
    shelley.run_cli(
        f"{shelley.cli} transaction sign "
        f"--tx-body-file {tx_file} {signing_key_args} {script_str}"
        f"{shelley.network} --out-file {tx_signed_file}"
    )

    # Return the path to the signed file for downstream use.
    return tx_signed_file


def mint_and_send(shelley,
        utxo,
        asset_owner_address,
        storage_address,
        token_assets,
        wallet_key=constants.WALLET_SKEY
        ):

    tx_name = datetime.now().strftime("tx_draft_%Y-%m-%d_%Hh%Mm%Ss") + "_" + str(uuid4())
    tx_draft_file = Path(shelley.working_dir) / (tx_name + ".draft")
    tx_raw_file = Path(shelley.working_dir) / (tx_name + ".raw")

    if type(token_assets) != list:
        token_assets = [token_assets, ]

    ada_min_value = constants.ASSET_ADA_MIN + 300000 * (len(token_assets) - 1) # TODO: Magic. Would be nice to find some real formula

    spare_ada = int(utxo['Lovelace']) - ada_min_value

    tip = shelley.get_tip()
    ttl = tip + shelley.ttl_buffer

    sending_tokens = []
    minting_tokens = []
    merged_metadata = token_assets[0].metadata
    for token_asset in token_assets:
        sending_tokens.append(f"+\"1 {constants.POLICY_HASH}.{token_asset.name}\"")
        minting_tokens.append(f"\"1 {constants.POLICY_HASH}.{token_asset.name}\"")

        merged_metadata['721'][constants.POLICY_HASH].update(token_asset.metadata['721'][constants.POLICY_HASH])

    sending_tokens = ''.join(sending_tokens)
    minting_tokens = '+'.join(minting_tokens)


    json_path = constants.TOKENS_PATH / f"doggies_multiple.json"
    with open(json_path, 'w') as f:
        f.write(json.dumps(merged_metadata))

    print(merged_metadata)
    print(minting_tokens)
    print(sending_tokens)

    # Construct raw no-fees
    command = (
            f"{shelley.cli} transaction build-raw "
            f"--fee 0 "
            f"--ttl {ttl} "
            f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "
            f"--tx-out {asset_owner_address}+{ada_min_value}"
            f"{sending_tokens}"
            " "
            f"--tx-out {storage_address}+{spare_ada} "
            f"--metadata-json-file {json_path} "
            f"--mint {minting_tokens} "
            f"--out-file {tx_draft_file}"
            )
    print(command)

    results = shelley.run_cli(command)
    print(results.stderr)
    assert not results.stderr

    # shelley.load_protocol_parameters() - it is being executed by the calc_min_fee already

    min_fee = shelley.calc_min_fee(tx_draft_file, tx_in_count=1, tx_out_count=2, witness_count=2)

    print(f"MIN FEE: {min_fee}")

    spare_ada = spare_ada - min_fee

    # Build the transaction again
    command = (
            f"{shelley.cli} transaction build-raw "
            f"--fee {min_fee} "
            f"--ttl {ttl} "
            f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "
            f"--tx-out {asset_owner_address}+{ada_min_value}"
            f"{sending_tokens}"
            " "
            f"--tx-out {storage_address}+{spare_ada} "
            f"--metadata-json-file {json_path} "
            f"--mint {minting_tokens} "
            f"--out-file {tx_raw_file}"
            )

    results = shelley.run_cli(command)
    assert not results.stderr

    tx_signed_file = sign_transaction(shelley,tx_raw_file, [
                                                            wallet_key,
                                                            constants.POLICY_SKEY
                                                           ],
                                                           script=constants.POLICY_SCRIPT)

    trans_results = shelley.submit_transaction(tx_signed_file)

    return (spare_ada, trans_results)


def send_back(shelley,
        utxo,
        asset_owner_address,
        ):

    tx_name = datetime.now().strftime("tx_draft_%Y-%m-%d_%Hh%Mm%Ss") + "_" + str(uuid4())
    tx_draft_file = Path(shelley.working_dir) / (tx_name + ".draft")
    tx_raw_file = Path(shelley.working_dir) / (tx_name + ".raw")

    spare_ada = int(utxo['Lovelace'])

    tip = shelley.get_tip()
    ttl = tip + shelley.ttl_buffer


    # Construct raw no-fees
    command = (
            f"{shelley.cli} transaction build-raw "
            f"--fee 0 "
            f"--ttl {ttl} "
            f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "
            f"--tx-out {asset_owner_address}+{spare_ada} "
            f"--out-file {tx_draft_file}"
            )

    results = shelley.run_cli(command)
    assert not results.stderr

    # shelley.load_protocol_parameters() - it is being executed by the calc_min_fee already

    min_fee = shelley.calc_min_fee(tx_draft_file, tx_in_count=1, tx_out_count=1, witness_count=1)

    spare_ada = spare_ada - min_fee

    # Build the transaction again
    command = (
            f"{shelley.cli} transaction build-raw "
            f"--fee {min_fee} "
            f"--ttl {ttl} "
            f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "
            f"--tx-out {asset_owner_address}+{spare_ada} "
            f"--out-file {tx_raw_file}"
            )

    results = shelley.run_cli(command)
    assert not results.stderr

    tx_signed_file = sign_transaction(shelley,tx_raw_file, [
                                                            constants.WALLET_SKEY,
                                                           ],
                                     )

    trans_results = shelley.submit_transaction(tx_signed_file)

    return(trans_results)


