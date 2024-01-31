from gcloud.aio.auth import Token
from gcloud.aio.storage import Storage

SCOPES = ["https://www.googleapis.com/auth/cloud-platform.read-only"]
TIMEOUT = 30


async def get_storage_token(service_file: str ) -> Token:

    try:
        _ = Token(service_file=service_file, scopes=SCOPES)
        return _
    except Exception as e:
        raise e


async def list_storage_objects(bucket_name: str, token: Token, prefix: str = "") -> tuple:

    try:
        objects = []
        params = {'prefix': prefix}
        async with Storage(token=token) as storage:
            while True:
                _ = await storage.list_objects(bucket_name, params=params, timeout=TIMEOUT)
                objects.extend(_.get('items', []))
                params['pageToken'] = _.get('nextPageToken')
                if not params.get('pageToken'):
                    break
    except Exception as e:
        await storage.close()
        raise e

    return tuple([obj['name'] for obj in objects if int(obj.get('size', 0)) != 0])


async def get_storage_object(bucket_name: str, token: Token, object_name: str) -> bytes:

    try:
        blob = "".encode()
        async with Storage(token=token) as storage:
            blob = await storage.download(bucket_name, object_name, timeout=TIMEOUT)
    except Exception as e:
        await storage.close()
        raise e

    return blob
