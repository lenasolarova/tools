

import json
import tarfile
import click
import os 
import logging 
import requests
from io import BytesIO
from molodec.archive_producer import ArchiveProducer
from molodec.crc import CONTENT_TYPE
from molodec.renderer import Renderer
from molodec.rules import RuleSet
from requests.auth import HTTPBasicAuth
from iqe_jwt import OIDCAuth
from iqe_jwt import TokenSrc

"""
You need to install molodec first

export PIP_INDEX_URL=https://repository.engineering.redhat.com/nexus/repository/insights-qe/simple
pip install -U molodec

upload with: python script.py upload <optionally options>
"""


CLUSTER_ID = "18000000-c53b-4ea9-ae22-ac4415e2cf21"

_REFRESH_TOKEN = "eyJhbGciOiJIUzUxMiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI0NzQzYTkzMC03YmJiLTRkZGQtOTgzMS00ODcxNGRlZDc0YjUifQ.eyJpYXQiOjE3NTQ4OTA4MDMsImp0aSI6IjgyNjdiYmNhLTFmM2EtNDRiZC1hZWVjLTM5ZWM0ODExZmMwZSIsImlzcyI6Imh0dHBzOi8vc3NvLnJlZGhhdC5jb20vYXV0aC9yZWFsbXMvcmVkaGF0LWV4dGVybmFsIiwiYXVkIjoiaHR0cHM6Ly9zc28ucmVkaGF0LmNvbS9hdXRoL3JlYWxtcy9yZWRoYXQtZXh0ZXJuYWwiLCJzdWIiOiJmOjUyOGQ3NmZmLWY3MDgtNDNlZC04Y2Q1LWZlMTZmNGZlMGNlNjpyaC1lZS1sc29sYXJvdiIsInR5cCI6Ik9mZmxpbmUiLCJhenAiOiJyaHNtLWFwaSIsInNpZCI6ImM5MjZhYjc4LWNiM2YtNDUzNi1hOTExLTBiYmM4NDVlNjk3OSIsInNjb3BlIjoiYmFzaWMgcm9sZXMgd2ViLW9yaWdpbnMgY2xpZW50X3R5cGUucHJlX2tjMjUgb2ZmbGluZV9hY2Nlc3MifQ.hy0BAKKk5XhjDzNo8MidhMVKw-h6Cf73hqyw9ZlEu6mZki_PneKXn-1u5BrzhF8qGkBF0_UU6iNOch_vQJUSww"

_TOKEN_URL = os.environ.get(
    "TOKEN_URL", "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
)

#stage variables
_STAGE_PULL_SECRET_URL = os.environ.get(
    "PULL_SECRET_URL", "https://api.stage.openshift.com/api/accounts_mgmt/v1/access_token"
)
STAGE_INGRESS_UPLOAD="https://console.stage.redhat.com/api/ingress/v1/upload"

#prod variables
_PROD_PULL_SECRET_URL = os.environ.get(
    "PULL_SECRET_URL", "https://api.openshift.com/api/accounts_mgmt/v1/access_token"
)
PROD_INGRESS_UPLOAD="https://console.redhat.com/api/ingress/v1/upload"


logger = logging.getLogger(__name__)

def setup():
    token_src = TokenSrc("rhsm-api", _TOKEN_URL)
    oidc_auth = OIDCAuth.from_refresh_token(_REFRESH_TOKEN, token_src, scope="offline_access")
    r = requests.post(_STAGE_PULL_SECRET_URL, auth=oidc_auth)
    openshift_com_token = r.json()["auths"]["cloud.openshift.com"]["auth"]

    return openshift_com_token


def upload_ocp_recommendations():
    openshift_com_token = setup()

    producer = ArchiveProducer(Renderer(*RuleSet("io").get_default_rules()))
    tario = producer.make_tar_io(CLUSTER_ID)

    headers = {
        "Authorization": f"Bearer {openshift_com_token}",
        "User-Agent": f"insights-operator/360ca33afd09b4aa0796a79350234c6a68d9ee9e cluster/{CLUSTER_ID}",
    }
    
    r = requests.post(
        STAGE_INGRESS_UPLOAD,
        files={"file": ("archive", tario.getvalue(), CONTENT_TYPE)},
        headers=headers,
    )

    print(f"Status Code: {r.status_code}")
    print(f"Response Content: {r.text}")
    print("cluser id:", CLUSTER_ID)
    print("sent to:", CONTENT_TYPE)


def upload_ols(content_type):
    openshift_com_token = setup()

    headers = {
        "Authorization": f"Bearer {openshift_com_token}",
        "User-Agent": f"insights-operator/360ca33afd09b4aa0796a79350234c6a68d9ee9e cluster/{CLUSTER_ID}",
    }

    tario = BytesIO()
    tar = tarfile.open(fileobj=tario, mode="w:gz")

    try:
        tar_info = tarfile.TarInfo("openshift_lightspeed.json")
        tar_info.size = 0
        tar.addfile(tar_info)

        #should not be necessary anymore
        #tar_info = tarfile.TarInfo("config/id")
        content = bytes(CLUSTER_ID, "utf-8")
        tar_info.size = len(content)
        tar.addfile(tar_info, fileobj=BytesIO(content))

    except:
        raise
    finally:
        tar.close()

    r = requests.post(
        STAGE_INGRESS_UPLOAD,
        files={"file": ("archive", tario.getvalue(), content_type)},
        headers=headers,
    )

    print(f"Status Code: {r.status_code}")
    print(f"Response Content: {r.text}")
    print("cluser id:", CLUSTER_ID)
    print("sent to:", content_type)

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    pass


@cli.command("upload")
@click.option("--ols", default=False, is_flag=True)
@click.option("--olscopy", default=False, is_flag=True)

def _upload(ols, olscopy):
    if ols:
        upload_ols(content_type=CONTENT_TYPE)
    elif olscopy:
        upload_ols(content_type="application/vnd.redhat.ols.periodic+tar")
    else:
        upload_ocp_recommendations()


if __name__ == "__main__":
    cli()
