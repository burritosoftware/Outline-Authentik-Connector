import authentik_client
from dotenv import load_dotenv
import os
import logging
import re

load_dotenv()
logger = logging.getLogger("oa-connector")

# Presence guaranteed by startup validation in connect.py; use os.environ so a runtime
# regression (var emptied/unset) raises KeyError instead of silently authing as anonymous.
authentik_config = authentik_client.Configuration(
    host = f"{os.environ['AUTHENTIK_URL']}/api/v3",
    access_token=os.environ['AUTHENTIK_TOKEN']
)

group_pattern=os.getenv('SYNC_GROUP_REGEX', default=None)
group_regex = None
if group_pattern:
    try:
        group_regex = re.compile(group_pattern, re.IGNORECASE)
    except re.error as e:
        logger.error(
            f"Invalid SYNC_GROUP_REGEX {group_pattern!r}: {e}. "
            "Fix the pattern or unset SYNC_GROUP_REGEX to disable filtering."
        )
        raise RuntimeError(f"Invalid SYNC_GROUP_REGEX: {e}") from e

def get_authentik_groups_of_user(email: str) -> list:
    authentik_groups = []
    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        users_response = api_instance.core_users_list(email=email)

        if not users_response.results:
            logger.debug(f"No Authentik user found with email {email}")
            return authentik_groups

        authentik_user = users_response.results[0]
        for group in authentik_user.groups_obj:
            # Apply regex filtering if a pattern is provided
            if (group_regex and group_regex.match(group.name)) or not group_regex:
                authentik_groups.append(group.name)

    logger.info(f"Got {len(authentik_groups)} groups for user {email} from Authentik (after regex filtering, if applied)")
    
    return authentik_groups
