#!/usr/bin/env python3

from os import environ, system
from os import path
from sys import argv, exit
import yaml
import json

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
PWD = path.realpath(path.dirname(__file__))
ADC_VAR = 'GOOGLE_APPLICATION_CREDENTIALS'
ENVIRONMENTS_FILE = "environments.yaml"


def get_environments(input_file: str = ENVIRONMENTS_FILE) -> dict:
    """
    Get environments
    """
    _ = path.join(PWD, str(input_file))
    assert path.exists(_), f"File '{_}' does not exist"
    assert path.isfile(_), f"File '{_}' is not a file"
    fp = open(_, mode="rb")
    _ = yaml.load(fp, Loader=yaml.FullLoader)
    fp.close()
    return _


def set_environment(key_file: str) -> str:
    
    key_path = path.realpath(path.join(PWD, key_file))
    print(key_path)
    assert path.exists(key_path), f"File '{key_path}' does not exist"
    assert path.isfile(key_path), f"File '{key_path}' is not a file"

    with open(key_path, mode="rb") as fp:
        key_json = json.load(fp)
    if client_email := key_json.get('client_email'):
        system(f"gcloud auth activate-service-account {client_email} --key-file=\"{key_path}\"")
        environ.update({ADC_VAR: key_path})
    else:
        raise KeyError(f"Could not find key 'client_mail' in JSON file '{key_path}'")

    return client_email


def main(environment: str) -> str:

    environments = get_environments()
    assert environment in environments, f"environment '{environment}' not found"
    env = environments.get(environment)
    if google_adc_key := env.get('google_adc_key'):
        _ = set_environment(google_adc_key)
        return _


if __name__ == "__main__":

    if len(argv) <= 1:
        exit("Usage: " + argv[0] + " <environment>")

    e = argv[1]
    if _ := main(e):
        print(f"Environment '{e}' activated successfully as {_}")
