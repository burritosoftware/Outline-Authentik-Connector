import authentik_client
from dotenv import load_dotenv
import os
import logging

load_dotenv()
logger = logging.getLogger("oa-connector")

authentik_config = authentik_client.Configuration(
    host = f"{os.getenv('AUTHENTIK_URL')}/api/v3",
    access_token=os.getenv('AUTHENTIK_TOKEN')
)

def get_authentik_groups():
    authentik_groups = []

    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        groups_list = api_instance.core_groups_list(include_users=False).results
        for group in groups_list:
            authentik_groups.append(group.name)

    logger.info(f"Got {len(authentik_groups)} groups from Authentik")
    return(authentik_groups)