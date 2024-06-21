# Outline Authentik Connector
![Icons](https://skillicons.dev/icons?i=py,fastapi,docker)

[![WakaTime](https://wakatime.com/badge/github/burritosoftware/Outline-Authentik-Connector.svg)](https://wakatime.com/badge/github/burritosoftware/Outline-Authentik-Connector) ![Docker Pulls](https://img.shields.io/docker/pulls/burritosoftware/outline-authentik-connector?logo=docker&logoColor=white)

Syncs groups between Authentik and Outline. Users will be added/removed from Outline groups depending on what Authentik groups they're in, on each sign in.

This was inspired by [this similar connector for Outline and Keycloak](https://gist.github.com/Frando/aa561ca7e6c72ab64b5d17df911c0b1f)! I created this for internal use at [WiiLink](https://github.com/WiiLink24) and to learn FastAPI and Docker.

## How It Works
Outline groups that are named the same as Authentik groups will be linked together. Users who are in an Authentik group but not in a linked Outline group will be added to the Outline group. Conversely, if a user is not in a linked Authentik group, but is in an Outline group, they will be removed from that group.

This connector listens for `users.signin` webhook events from Outline. Once a user signs into Outline, this connector will check for matching groups, and add/remove the user to those groups accordingly.

## Requirements
- Outline API key
- Authentik API key
- Reverse proxy to apply HTTPS
- Python 3.11.1 or higher (not required if using Docker)
- Docker and Docker Compose (optional)

## Outline Setup
1. Login to your Outline instance. Click your profile in the bottom left, then go to **Preferences**.
2. On the sidebar, click **API**. At the top right, select **New API Key...**, and give it a name like `Outline Authentik Connector`.
3. Save the API key somewhere safe to fill in later.
4. On the sidebar, click **Webhooks**. At the top right, select **New webhook...**, and give it a name like `Outline Authentik Connector`. Copy the signing secret and save it somewhere safe to fill in later.
5.  Enter in the URL of a subdomain you plan to host the connector on. Then, tick the box for **users.signin**, and then scroll all the way down and click **Create**.

## Authentik Setup
1. Login to your Authentik instance, and access the **Admin interface**.
2. On the sidebar, go to **Directory > Tokens and App passwords**. Click the blue **Create** button.
3. Set an identifier for the token and which user you want to bind this to (typically, yourself). Make sure the intent is **API Token**. Turn off **Expiring** unless you want to rotate the token manually after expiry.
4. Click **Copy token** next to the token you made, and save it somewhere safe to fill in later.

Now, choose whether to setup the connector [with Docker](#docker-setup) or [manually](#manual-setup).

## Docker Setup
The connector can be deployed with Docker Compose for quick and easy setup.
1. [Grab the `docker-compose.yml` file here](./docker-compose.yml), as well as [the `.env.example` file here](./.env.example).
2. Change `.env.example` to `.env`, and fill it in with your Authentik and Outline configuration.
3. Start the connector with `docker compose up -d`. By default, the connector will be exposed on port `8430`.
4. Use a reverse proxy to proxy the connector to a subdomain with HTTPS.

## Manual Setup
1. Install requirements.
```sh
pip3 install -r requirements.txt
```
2. Copy the environment configuration, and fill it in with your Authentik and Outline configuration.
```sh
cp .env.example .env
nano .env
```

3. Start the connector.
```sh
fastapi run connect.py --port 8430
```
4. Use a reverse proxy to proxy the connector to a subdomain with HTTPS.