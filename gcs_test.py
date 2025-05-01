from asyncio import run
from file_utils import *
from gcp_utils import *


async def main():

    environments = await get_environments()
    for e, environment in environments.items():
        if google_adc_key := environment.get('google_adc_key'):
            service_file = PWD.joinpath(google_adc_key)
            token = Token(service_file=str(service_file), scopes=SCOPES)
            if bucket_name := environment.get('bucket_name'):
                _ = await list_gcs_objects(bucket_name, token)
                print(["{}:{}".format(o['name'], o['size']) for o in _])
            await token.close()

if __name__ == "__main__":

    run(main())