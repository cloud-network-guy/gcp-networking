from asyncio import run
from gcp_utils import get_access_token


async def main():

    try:
        access_token = await get_access_token()
    except Exception as e:
        quit(e)
    return access_token


if __name__ == '__main__':

    _ = run(main())
    print(_)


