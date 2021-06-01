from os import path
import json

import constants

class Token(object):
    name=None
    json_path=None
    metadata = None

    def __init__(self, name, metadata, json_path):
        self.name = name
        self.json_path = json_path
        self.metadata = metadata

        assert path.exists(json_path)


class DBToken(object):
    key = None
    reserved_until = None
    doggie_id = None
    doggie_metadata = None
    doggie_image = None

    def __init__(self):
        pass

def token_constructor(token_id, metadata):
    # Simplified token cosntructor
    json_path = constants.TOKENS_PATH / f"token{token_id}.json"
    with open(json_path, 'w') as f:
        f.write(metadata)

    json_data = json.loads(metadata)

    # Get Token Name

    # Get to 721 item
    item_721 = list(list(json_data.values())[0].values())[0]
    # Get to policy hash item
    item_policy = list(item_721.values())[0]
    # Finally the token name
    token_name = list(item_721.keys())[0]

    t = Token(token_name, json_data, json_path)

    return t

def doggie_token_constructor(doggie_id, metadata):
    json_path = constants.TOKENS_PATH / f"doggie{doggie_id}.json"
    with open(json_path, 'w') as f:
        f.write(json.dumps(metadata))

    t = Token(f"CryptoDoggie{doggie_id}", metadata, json_path)

    return t
