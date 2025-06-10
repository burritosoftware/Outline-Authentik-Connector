import httpx
import inspect
import asyncio

original_init = httpx.AsyncClient.__init__

def patched_init(self, *args, **kwargs):
    if 'proxies' in kwargs and 'proxies' not in inspect.signature(original_init).parameters:
        del kwargs['proxies']
    original_init(self, *args, **kwargs)

httpx.AsyncClient.__init__ = patched_init

import authentik_client
from outline import AsyncOutline
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import json
import os
import logging
import hmac
import hashlib

import helpers.authentik
import helpers.outline

load_dotenv()

app = FastAPI()

# Logging setup
logger = logging.getLogger("oa-connector")
if os.getenv('DEBUG') == "True":
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s:     %(name)s: %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

authentik_config = authentik_client.Configuration(
    host = f"{os.getenv('AUTHENTIK_URL')}/api/v3",
    access_token=os.getenv('AUTHENTIK_TOKEN')
)

outline_client = AsyncOutline(
    bearer_token=os.getenv('OUTLINE_TOKEN'),
    base_url=os.getenv('OUTLINE_URL')
)

@app.get("/")
def root():
    return({'status': 'running'})

@app.post("/sync")
async def sync(request: Request):
    logger.debug("Received webhook")
    # Verifying webhook signature using secret
    body = await request.body()
    outline_signature_header = request.headers.get('outline-signature')
    if not outline_signature_header:
        logger.debug("Request is missing signature")
        return({'status': 'missing-signature'})

    parts = outline_signature_header.split(',')
    if len(parts) != 2:
        logger.debug("Request signature is invalid")
        return({'status': 'invalid-signature'})

    timestamp = parts[0].split('=')[1]
    signature = parts[1].split('=')[1]

    full_payload = f"{timestamp}.{body.decode('utf-8')}"

    digester = hmac.new(os.getenv('OUTLINE_WEBHOOK_SECRET').encode('utf-8'), full_payload.encode('utf-8'), hashlib.sha256)
    calculated_signature = digester.hexdigest()

    if not hmac.compare_digest(signature, calculated_signature):
        logger.debug("Signature calculation failed")
        return({'status': 'unauthorized'})

    logger.debug("Signature verified, continuing...")
    # Processing Outline webhook payload
    response = await request.json()
    payload = response['payload']
    model = payload['model']
    outline_id = model['id']

    if response['event'] != 'users.signin':
        return({'status:': 'wrong-event'})
    
    # Using helper methods to grab groups
    authentik_groups = helpers.authentik.get_authentik_groups()
    
    outline_groups = await helpers.outline.get_outline_groups()
    
    logger.debug(f"Authentik groups: {authentik_groups}")
    logger.debug(f"Outline groups: {[list(g.keys())[0] for g in outline_groups]}")

    matched_groups = []
    auth_to_outline_map = {}
    user_authentik_groups = []
    user_outline_groups = []

    # Matching groups together by name
    for name in authentik_groups:
        logger.debug(f"Looking to match Authentik group: {name}")
        for outline_group in outline_groups:
            outline_group_name = list(outline_group.keys())[0]
            logger.debug(f"Comparing with Outline group: {outline_group_name}")
            
            if name.lower() == outline_group_name.lower():
                logger.debug(f"Direct match found: {name} with {outline_group_name}")
                matched_groups.append(outline_group)
                auth_to_outline_map[name] = outline_group_name
                break
                
            auth_normalized = name.lower().replace("-", "").replace(" ", "").replace("_", "")
            outline_normalized = outline_group_name.lower().replace("-", "").replace(" ", "").replace("_", "")
            
            if auth_normalized == outline_normalized:
                logger.debug(f"Normalized match found: {name} with {outline_group_name}")
                matched_groups.append(outline_group)
                auth_to_outline_map[name] = outline_group_name
                break
                
    logger.info(f"Matched {len(matched_groups)} groups: {[list(g.keys())[0] for g in matched_groups]}")
    if auth_to_outline_map:
        logger.debug(f"Group mappings: {auth_to_outline_map}")

    user_response = await outline_client.post(path='/api/users.info', cast_to=httpx.Response, body={'id': outline_id})
    user = json.loads(await user_response.aread())
    email = user['data']['email']
    logger.debug(f"Processing user: {email}")

    # Getting Authentik user's groups
    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        
        try:
            user_results = api_instance.core_users_list(email=email).results
            
            if not user_results:
                logger.info(f"No exact email match for {email}, trying case-insensitive search")
                all_users = api_instance.core_users_list().results
                for user_obj in all_users:
                    if user_obj.email and user_obj.email.lower() == email.lower():
                        user_results = [user_obj]
                        logger.info(f"Found user with case-insensitive match: {user_obj.email}")
                        break
            
            if not user_results:
                logger.warning(f"User with email {email} (case-insensitive) not found in Authentik")
                return {'status': 'user-not-found-in-authentik'}
            
            authentik_user = user_results[0]
            logger.debug(f"All user groups from Authentik: {[obj.name for obj in authentik_user.groups_obj]}")
            
            matched_group_names = [list(kv.keys())[0] for kv in matched_groups]
            for obj in authentik_user.groups_obj:
                logger.debug(f"Checking if {obj.name} is in matched groups: {matched_group_names}")
                
                if obj.name in matched_group_names:
                    user_authentik_groups.append(obj.name)
                    logger.debug(f"Added {obj.name} to user's Authentik groups")
                elif obj.name in auth_to_outline_map:
                    outline_name = auth_to_outline_map[obj.name]
                    user_authentik_groups.append(outline_name)
                    logger.debug(f"Added mapped group {obj.name} → {outline_name} to user's groups")
                
        except Exception as e:
            logger.error(f"Error retrieving user from Authentik: {e}")
            return {'status': 'authentik-error', 'error': str(e)}
        
    logger.debug(f"User's matched Authentik groups: {user_authentik_groups}")

    # Getting Outline user's groups
    for group in outline_groups:
        group_id = list(group.values())[0]
        group_name = list(group.keys())[0]
        membership = await helpers.outline.get_group_membership(group_id, outline_id, user['data']['name'])
        if membership:
            user_outline_groups.append(group_id)
            logger.debug(f"User is member of Outline group '{group_name}' (ID: {group_id})")

    logger.debug(f"Got {len(user_outline_groups)} user groups from Outline")

    # Adding user to matched groups, removing user from unmatched groups
    for group in matched_groups:
        group_name = list(group.keys())[0]
        group_id = list(group.values())[0]

        if group_name in user_authentik_groups:
            if group_id not in user_outline_groups:
                logger.info(f"Adding user to group '{group_name}' (ID: {group_id})")
                await helpers.outline.add_user_to_group(group_id, outline_id)
            else:
                logger.debug(f"User is already in group '{group_name}' (ID: {group_id}), not adding")
        else:
            if group_id in user_outline_groups:
                logger.info(f"Removing user from group '{group_name}' (ID: {group_id})")
                await helpers.outline.remove_user_from_group(group_id, outline_id)
            else:
                logger.debug(f"User is not in group '{group_name}' (ID: {group_id}), not removing")

    logger.info("Sync complete!")
    return({'status': 'success'})