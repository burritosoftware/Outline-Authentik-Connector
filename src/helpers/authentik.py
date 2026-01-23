import authentik_client
from dotenv import load_dotenv
import os
import logging
import re

load_dotenv()
logger = logging.getLogger("oa-connector")

authentik_config = authentik_client.Configuration(
    host = f"{os.getenv('AUTHENTIK_URL')}/api/v3",
    access_token=os.getenv('AUTHENTIK_TOKEN')
)

group_pattern=os.getenv('AUTHENTIK_GROUP_REGEX', default=None)
group_regex = None
if group_pattern:
    group_regex = re.compile(group_pattern,re.IGNORECASE)


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
                # Apply regex filtering if a pattern is provided
                if (group_regex and group_regex.match(group.name)) or not group_regex:
                    authentik_groups.append(group.name)

            if groups_response.pagination.next:
                page_num += 1
            else:
                has_more = False
            
            logger.debug(f"Fetched {len(authentik_groups)} groups from Authentik API, page {page_num}, has_more: {has_more}")

    logger.info(f"Got {len(authentik_groups)} groups from Authentik across {page_num} pages (after regex filtering, if applied)")
    
    return(authentik_groups)
