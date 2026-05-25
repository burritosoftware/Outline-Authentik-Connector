from fastapi import FastAPI, Request, HTTPException

from dotenv import load_dotenv
import os
import logging
import hmac
import hashlib
import json
import time

import helpers.authentik
import helpers.outline


def _parse_outline_signature(header: str) -> tuple[str, str]:
    # Outline sends `t=<timestamp>,s=<hex>`; tolerate reordered or extra fields,
    # but reject anything that doesn't yield exactly one of each.
    timestamp = None
    signature = None
    for part in header.split(','):
        key, sep, value = part.strip().partition('=')
        if not sep or not value:
            raise ValueError("malformed signature segment")
        if key == 't':
            timestamp = value
        elif key == 's':
            signature = value
    if timestamp is None or signature is None:
        raise ValueError("missing t= or s= in signature header")
    return timestamp, signature

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

# Configure httpx logger to only show in debug mode
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG if level == logging.DEBUG else logging.WARNING)


# Configuration for automatic group creation
AUTO_CREATE_GROUPS = os.getenv('AUTO_CREATE_GROUPS', False).lower() == 'true'

# Reject webhooks whose signed timestamp drifts beyond this window (seconds).
WEBHOOK_TOLERANCE_SECONDS = int(os.getenv('WEBHOOK_TOLERANCE_SECONDS', '300'))

# Defense-in-depth body size cap before signature verification.
MAX_BODY_BYTES = int(os.getenv('MAX_BODY_BYTES', '1048576'))

@app.get("/")
def root():
    return({'status': 'running'})

@app.post("/sync")
async def sync(request: Request):
    logger.debug("Received webhook")

    # Reject obviously oversized bodies before reading them into memory.
    declared_length = request.headers.get('content-length')
    if declared_length is not None:
        try:
            if int(declared_length) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="request body too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid Content-Length")

    # Stream the body so a missing or lying Content-Length can't smuggle past the cap.
    body = b''
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="request body too large")
    outline_signature_header = request.headers.get('outline-signature')
    if not outline_signature_header:
        logger.debug("Request is missing signature")
        return({'status': 'missing-signature'})

    try:
        timestamp, signature = _parse_outline_signature(outline_signature_header)
    except ValueError:
        logger.debug("Request signature header is malformed")
        raise HTTPException(status_code=400, detail="malformed signature header")

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        logger.debug("Signature timestamp is not an integer")
        raise HTTPException(status_code=400, detail="malformed signature header")

    if abs(time.time() - timestamp_int) > WEBHOOK_TOLERANCE_SECONDS:
        logger.warning("Rejecting webhook: timestamp outside tolerance window")
        raise HTTPException(status_code=401, detail="stale timestamp")

    full_payload = f"{timestamp}.{body.decode('utf-8')}"

    digester = hmac.new(os.getenv('OUTLINE_WEBHOOK_SECRET').encode('utf-8'), full_payload.encode('utf-8'), hashlib.sha256)
    calculated_signature = digester.hexdigest()

    if not hmac.compare_digest(signature, calculated_signature):
        logger.debug("Signature calculation failed")
        return({'status': 'unauthorized'})

    logger.debug("Signature verified, continuing...")

    # Processing Outline webhook payload (body was already consumed above)
    response = json.loads(body)
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
    