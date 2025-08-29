import authentik_client
from outline import AsyncOutline
from fastapi import FastAPI, Request

import httpx
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

# Configuration for automatic group creation
AUTO_CREATE_GROUPS = os.getenv('AUTO_CREATE_GROUPS', False).lower() == 'true'

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

    # Getting Outline user's email
    user_response = await outline_client.post(path='/api/users.info', cast_to=httpx.Response, body={'id': outline_id})
    user = json.loads(await user_response.aread())
    email = user['data']['email']

    # Getting Authentik user's groups
    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        authentik_user = api_instance.core_users_list(email=email).results[0]
        user_authentik_groups = [obj.name for obj in authentik_user.groups_obj]

    logger.debug(f"User is member of {len(user_authentik_groups)} groups in Authentik")

    # Create a map of outline groups for easier lookup
    outline_groups_map = {}
    for group in outline_groups:
        group_name = list(group.keys())[0]
        group_id = list(group.values())[0]
        outline_groups_map[group_name] = group_id

    # Process each Authentik group
    for authentik_group_name in authentik_groups:
        # Check if user is member of this group in Authentik
        user_is_member_in_authentik = authentik_group_name in user_authentik_groups
        
        # Check if user is member of this group in Outline
        user_is_member_in_outline = False
        outline_group_id = outline_groups_map.get(authentik_group_name)
        if outline_group_id:
            membership = await helpers.outline.get_group_membership(outline_group_id, outline_id, user['data']['name'])
            user_is_member_in_outline = membership
        
        # User is NOT member in Authentik but IS member in Outline -> Remove from Outline
        if not user_is_member_in_authentik and user_is_member_in_outline:
            logger.info(f"Removing user from Outline group '{authentik_group_name}'")
            await helpers.outline.remove_user_from_group(outline_group_id, outline_id)
        
        # User IS member in Authentik
        elif user_is_member_in_authentik:
            # Check if group exists in Outline
            if not outline_group_id:
                # Group does not exist in Outline and auto-creation is enabled -> create it
                if AUTO_CREATE_GROUPS:
                    logger.info(f"Creating missing group '{authentik_group_name}' in Outline")
                    create_status, new_group_id = await helpers.outline.create_group(authentik_group_name)
                    if create_status == 200 and new_group_id:
                        outline_group_id = new_group_id
                        outline_groups_map[authentik_group_name] = outline_group_id
                    else:
                        logger.error(f"Failed to create group '{authentik_group_name}' in Outline")
                        continue
                else: # Group does not exist in Outline and auto-creation is disabled
                    logger.debug(f"Group '{authentik_group_name}' doesn't exist in Outline and auto-creation is disabled")
                    continue
            
            # Add user to group if not already member
            if not user_is_member_in_outline:
                logger.info(f"Adding user to Outline group '{authentik_group_name}'")
                await helpers.outline.add_user_to_group(outline_group_id, outline_id)
            else:
                logger.debug(f"User is already member of group '{authentik_group_name}' in Outline")

    logger.info("Sync complete!")
    return({'status': 'success'})
    