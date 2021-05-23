import requests
from os import getenv
from dotenv import load_dotenv

load_dotenv()
URL_ADD_IPFS='https://api.pinata.cloud/pinning/pinFileToIPFS'

def get_headers(ipfs_account=None):
    key = ipfs_account or getenv('PINATA_JWT')
    return {'Authorization': f'Bearer {key}'}


def upload_to_ipfs(file_path, ipfs_account=None):
    headers = get_headers(ipfs_account)
    with open(file_path, 'rb') as f:
        files = {'file': f}

        response = requests.post(URL_ADD_IPFS, files=files, headers=headers)

        if response.status_code != 200:
            # Error
            raise Exception('Failed to upload to IPFS', response.text)

        results = response.json()

        return results['IpfsHash']

def pin_wrapper(url, delete=False):
    headers = get_headers()
    if not delete:
        response = requests.get(url, headers=headers)
    else:
        response = requests.delete(url, headers=headers)


    return response


def delete_all():
    r = pin_wrapper('https://api.pinata.cloud/data/pinList?status=pinned&pageLimit=1000')
    j = r.json()
    for row in j['rows']:
        url = f"https://api.pinata.cloud/pinning/unpin/{row['ipfs_pin_hash']}"
        response = pin_wrapper(url, delete=True)
        print(response)
