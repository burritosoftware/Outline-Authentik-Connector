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

group_pattern=os.getenv('SYNC_GROUP_REGEX', default=None)
group_regex = None
if group_pattern:
    group_regex = re.compile(group_pattern,re.IGNORECASE)

def get_authentik_groups_of_user(email: str) -> list:
    authentik_groups = []
    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        users_response = api_instance.core_users_list(email=email)

        if not users_response.results:
            logger.debug(f"No Authentik user found with email {email}")
            return authentik_groups

        # Authentik doesn't enforce email uniqueness; refusing ambiguous matches
        # prevents an Outline-side email change from inheriting another user's groups.
        # Pragmatic minimum -- proper fix is binding by OIDC `sub`, not email.
        # Check pagination.count first: duplicates may span pages and only show
        # one entry in results.
        total_count = getattr(getattr(users_response, 'pagination', None), 'count', None)
        if (total_count is not None and total_count > 1) or len(users_response.results) > 1:
            reported = total_count if total_count is not None else len(users_response.results)
            logger.warning(
                f"Refusing sync: {reported} Authentik users share email {email}"
            )
            return authentik_groups

        authentik_user = users_response.results[0]
        if (authentik_user.email or '').casefold() != email.casefold():
            logger.warning(
                f"Refusing sync: Authentik returned user with email "
                f"'{authentik_user.email}' for query '{email}'"
            )
            return authentik_groups

        for group in authentik_user.groups_obj:
            # Apply regex filtering if a pattern is provided
            if (group_regex and group_regex.match(group.name)) or not group_regex:
                authentik_groups.append(group.name)

    logger.info(f"Got {len(authentik_groups)} groups for user {email} from Authentik (after regex filtering, if applied)")
    
    return authentik_groups
