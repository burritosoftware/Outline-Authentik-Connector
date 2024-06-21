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

    matched_groups = []

    user_authentik_groups = []
    user_outline_groups = []

    # Matching groups together by name
    for name in authentik_groups:
        for outline_group in outline_groups:
            if name in outline_group:
                matched_groups.append(outline_group)
                break
    logger.info(f"Matched {len(matched_groups)} groups")

    # Getting Outline user's email
    user_response = await outline_client.post(path='/api/users.info', cast_to=httpx.Response, body={'id': outline_id})
    user = json.loads(await user_response.aread())
    email = user['data']['email']

    # Getting Authentik user's groups
    with authentik_client.ApiClient(authentik_config) as api_client:
        api_instance = authentik_client.CoreApi(api_client)
        authentik_user = api_instance.core_users_list(email=email).results[0]
        for obj in authentik_user.groups_obj:
            # Only adding user group if it is in matched_groups
            if obj.name in [list(kv.keys())[0] for kv in matched_groups]:
                user_authentik_groups.append(obj.name)
    logger.debug(f"Got {len(user_authentik_groups)} user groups from Authentik")

    # Getting Outline user's groups
    for group in outline_groups:
        group_id = list(group.values())[0]
        membership = await helpers.outline.get_group_membership(group_id, outline_id, user['data']['name'])
        if membership:
            user_outline_groups.append(group_id)

    logger.debug(f"Got {len(user_outline_groups)} user groups from Outline")

    # Adding user to matched groups, removing user from unmatched groups
    for group in matched_groups:
        group_name = list(group.keys())[0]
        group_id = list(group.values())[0]

        if group_name in user_authentik_groups:
            if group_id not in user_outline_groups: # User is in Authentik group but not in Outline group, add
                await helpers.outline.add_user_to_group(group_id, outline_id)
            else: # User is in both Authentik and Outline groups already
                logger.debug(f"User is already in group {group_id}, not adding")
        else:
            if group_id in user_outline_groups: # User is in Outline group but not in Authentik group, remove
                await helpers.outline.remove_user_from_group(group_id, outline_id)
            else: # User is not in either Authentik or Outline group
                logger.debug(f"User is already not in group {group_id}, not removing")

    logger.info("Sync complete!")
    return({'status': 'success'})
    