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
    page_num = 1
    has_more = True

    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        
        while has_more:
            logger.debug(f"Fetching Authentik groups page {page_num}")
            groups_response = api_instance.core_groups_list(include_users=False, page=page_num)
            
            for group in groups_response.results:
                authentik_groups.append(group.name)
            
            if groups_response.pagination.next:
                page_num += 1
            else:
                has_more = False

    logger.info(f"Got {len(authentik_groups)} groups from Authentik across {page_num} pages")
    return(authentik_groups)