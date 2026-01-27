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

async def get_outline_groups() -> list:
    outline_groups = []
    offset = 0
    limit = 100
    has_more_groups = True
    
    # Handle pagination to get all groups
    while has_more_groups:
        # Fetch groups
        outline_groups_response = await outline_client.post(
            path=f'/api/groups.list', 
            cast_to=httpx.Response,
            body={'limit': limit, 'offset': offset}
        )
        logger.debug(f"Fetching groups with offset {offset}")

        outline_groups_json = json.loads(await outline_groups_response.aread())
        groups = outline_groups_json['data']['groups']
        
        # Determine if there are more groups to fetch
        has_more_groups = len(groups) == limit

        # Append groups to the list
        for group in groups:
            outline_groups.append({group['name']: group['id']})

        # Increment offset for next batch
        offset += limit

    logger.info(f"Got {len(outline_groups)} groups from Outline")
    return (outline_groups)

async def get_group_membership(group_id, user_id, user_name):
    offset = 0
    limit = 100
    has_more_users = True
    
    # Handle pagination to get all group memberships
    while has_more_users:
        # Fetch group memberships
        outline_memberships_response = await outline_client.post(
            path=f'/api/groups.memberships', 
            cast_to=httpx.Response, 
            body={
                'id': group_id,
                'query': user_name,
                limit: limit,
                offset: offset
            }
        )
        logger.debug(f"Fetching memberships for group {group_id} with offset {offset}")

        outline_memberships_json = json.loads(await outline_memberships_response.aread())
        users = outline_memberships_json['data']['users']
        
        # Determine if there are more users to fetch
        has_more_users = len(users) == limit

        # Check in each of the [data][users] if user_id is in any of them
        for user in users:
            if user['id'] == user_id:
                logger.debug(f"User {user_name} is in group {group_id}")
                return (True)
        
        # Increment offset for next batch
        offset += limit
    
    logger.debug(f"User {user_name} is not in group {group_id}")
    return (False)

async def add_user_to_group(group_id, user_id):
    response = await outline_client.post(path='/api/groups.add_user', cast_to=httpx.Response, body={'id': group_id, 'userId': user_id})
    if response.status_code == 200:
        logger.debug(f"Added user {user_id} to group {group_id}")
    else:
        logger.error(f"Failed to add user {user_id} to group {group_id}")
    return(response.status_code)

async def remove_user_from_group(group_id, user_id):
    response = await outline_client.post(path='/api/groups.remove_user', cast_to=httpx.Response, body={'id': group_id, 'userId': user_id})
    if response.status_code == 200:
        logger.debug(f"Removed user {user_id} from group {group_id}")
    else:
        logger.error(f"Failed to remove user {user_id} from group {group_id}")
    return(response.status_code)

async def create_group(group_name):
    response = await outline_client.post(path='/api/groups.create', cast_to=httpx.Response, body={'name': group_name})
    if response.status_code == 200:
        logger.debug(f"Created group {group_name}")
        response_data = json.loads(await response.aread())
        group_id = response_data['data']['id']
        return (response.status_code, group_id)
    else:
        logger.error(f"Failed to create group {group_name}")
        return (response.status_code, None)

async def delete_group(group_id):
    response = await outline_client.post(path='/api/groups.delete', cast_to=httpx.Response, body={'id': group_id})
    if response.status_code == 200:
        logger.debug(f"Deleted group {group_id}")
    else:
        logger.error(f"Failed to delete group {group_id}")
    return(response.status_code)