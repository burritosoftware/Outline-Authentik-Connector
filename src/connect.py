from fastapi import FastAPI, Request

from dotenv import load_dotenv
import os
import logging
import hmac
import hashlib

import helpers.authentik
import helpers.outline

load_dotenv()

app = FastAPI()

# Logging setup
level = logging.DEBUG if os.getenv('DEBUG', 'False').lower() == 'true' else logging.INFO
logging.basicConfig(
    level=level,
    format='%(levelname)s:\t(%(name)s) %(message)s',
    handlers=[logging.StreamHandler()],
    force=True
)
logger = logging.getLogger("oa-connector")
logger.debug(f"Logging configured at level: {logging.getLevelName(level)}")

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
    
    # Getting Outline user's email
    user_email = await helpers.outline.get_outline_user_email(outline_id)

    # Get Authentik groups for the user
    user_authentik_groups = helpers.authentik.get_authentik_groups_of_user(user_email)

    # Get Outline groups for the user
    user_outline_groups = await helpers.outline.get_outline_groups(user_id=outline_id)
    
    # Determine groups to add and remove
    groups_to_add = [group for group in user_authentik_groups if group not in user_outline_groups.keys()]
    groups_to_remove = [group for group in user_outline_groups.keys() if group not in user_authentik_groups]
    
    # if there are groups to add, get all Outline groups
    all_outline_groups = {}
    if len(groups_to_add) > 0:
        all_outline_groups = await helpers.outline.get_outline_groups()

    # Groups to add
    for authentik_group_name in groups_to_add:
        # Get group ID in Outline
        outline_group_id = all_outline_groups.get(authentik_group_name)

        if not outline_group_id:
            if AUTO_CREATE_GROUPS:
                logger.info(f"Creating missing group '{authentik_group_name}' in Outline")
                create_status, new_group_id = await helpers.outline.create_group(authentik_group_name)
                
                if create_status == 200 and new_group_id:
                    outline_group_id = new_group_id
                elif create_status == 409:
                    # Group was created in the meantime, fetch all groups again
                    all_outline_groups = await helpers.outline.get_outline_groups()
                    outline_group_id = all_outline_groups.get(authentik_group_name)
                else:
                    # log already done in create_group
                    continue
            else:
                logger.debug(f"Group '{authentik_group_name}' doesn't exist in Outline and auto-creation is disabled")
                continue
        
        # Add user to group
        if await helpers.outline.add_user_to_group(outline_group_id, outline_id) == 200:
            logger.info(f"Added user to Outline group '{authentik_group_name}'")

    # Groups to remove
    for outline_group_name in groups_to_remove:
        # Get group ID in Outline
        outline_group_id = user_outline_groups.get(outline_group_name)
        
        if await helpers.outline.remove_user_from_group(outline_group_id, outline_id) == 200:
            logger.info(f"Removed user from Outline group '{outline_group_name}'")

    logger.info("Sync complete!")
    return({'status': 'success'})
    