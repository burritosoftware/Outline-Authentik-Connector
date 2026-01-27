from outline import AsyncOutline
from dotenv import load_dotenv
import httpx
import os
import json
import logging

load_dotenv()
logger = logging.getLogger("oa-connector")

outline_client = AsyncOutline(
    bearer_token=os.getenv('OUTLINE_TOKEN'),
    base_url=os.getenv('OUTLINE_URL')
)

async def get_outline_groups(query: str = None, user_id: str = None) -> dict:
    """
    Fetch all groups from Outline, optionally filtered by query or user_id.

    Args:
        query (str, optional): A search string to filter groups by name.
        user_id (str, optional): If provided, only groups containing this user will be returned
    
    Returns:
        dict: Dictionary with group names as keys and group IDs as values
    """
    
    outline_groups = {}
    offset = 0
    limit = 100
    has_more_groups = True
    
    # Handle pagination to get all groups
    while has_more_groups:
        # Create body query
        body = {'limit': limit, 'offset': offset}
        if query:
            body['query'] = query
        if user_id:
            body['userId'] = user_id

        # Fetch groups
        outline_groups_response = await outline_client.post(
            path=f'/api/groups.list', 
            cast_to=httpx.Response,
            body=body
        )
        logger.debug(f"Fetching groups with offset {offset}")

        outline_groups_json = json.loads(await outline_groups_response.aread())
        groups = outline_groups_json['data']['groups']
        
        # Determine if there are more groups to fetch
        has_more_groups = len(groups) == limit

        # Add groups to the dictionary
        for group in groups:
            outline_groups[group['name']] = group['id']

        # Increment offset for next batch
        offset += limit

    logger.info(f"Got {len(outline_groups)} groups from Outline")
    return outline_groups

async def add_user_to_group(group_id, user_id):
    response = await outline_client.post(
        path='/api/groups.add_user',
        cast_to=httpx.Response,
        body={'id': group_id, 'userId': user_id}
    )

    if response.status_code == 200:
        logger.debug(f"Added user {user_id} to group {group_id}")
    else:
        logger.error(f"Failed to add user {user_id} to group {group_id}")
    
    return response.status_code

async def remove_user_from_group(group_id, user_id):
    response = await outline_client.post(
        path='/api/groups.remove_user',
        cast_to=httpx.Response,
        body={'id': group_id, 'userId': user_id}
    )
    if response.status_code == 200:
        logger.debug(f"Removed user {user_id} from group {group_id}")
    else:
        logger.error(f"Failed to remove user {user_id} from group {group_id}")
    return response.status_code

async def create_group(group_name):
    response = await outline_client.post(
        path='/api/groups.create',
        cast_to=httpx.Response,
        body={'name': group_name}
    )

    if response.status_code == 200:
        logger.debug(f"Created group {group_name}")
        response_data = json.loads(await response.aread())
        group_id = response_data['data']['id']
        return response.status_code, group_id
    else:
        logger.error(f"Failed to create group {group_name}")
        return response.status_code, None
