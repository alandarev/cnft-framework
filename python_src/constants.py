from pathlib import Path
from os import getenv


MINTING_WALLET="minting_address"
MINTING_POLICY="minting_policy"
MINTING_ADDRESS=None
STORAGE_ADDRESS=None
TOKENS_PATH=None
ASSET_ADA_MIN=2000000
POLICY_HASH=None
WALLET_SKEY=None
POLICY_SKEY=None
POLICY_SCRIPT=None

MINTING_SENDER_ONLY_WALLET="minting_sender_address"
MINTING_SENDER_ONLY_ADDRESS=None
MINTING_SENDER_ONLY_KEY=None


def initiate_constants(shelley):
    globals().update(MINTING_ADDRESS = getenv("MINTING_ADDRESS"))
    globals().update(STORAGE_ADDRESS = getenv("STORAGE_ADDRESS"))
    globals().update(TOKENS_PATH = shelley.working_dir / "tokens")
    globals().update(WALLET_SKEY = shelley.working_dir / (MINTING_WALLET + ".skey"))
    globals().update(POLICY_SKEY = shelley.working_dir / "policy" / (MINTING_POLICY + ".skey"))
    globals().update(POLICY_SCRIPT = shelley.working_dir / "policy" / (MINTING_POLICY + ".script"))

    globals().update(MINTING_SENDER_ONLY_KEY = shelley.working_dir / (MINTING_SENDER_ONLY_WALLET + ".skey"))
    globals().update(MINTING_SENDER_ONLY_ADDRESS = getenv("MINTING_SENDER_ONLY_ADDRESS"))
    try:
        globals().update(POLICY_HASH = Path(shelley.working_dir / "policy" / (MINTING_POLICY + ".hash")).read_text().replace('\n',''))
    except:
        print("WARN: POLICY_HASH not loaded")
        pass

