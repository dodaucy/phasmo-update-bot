# Phasmo Update Bot

Send blog and trello updates in a Discord chat via webhooks.

## Examples

![Blog Example](/img/blog.png)

![Trello Example](/img/trello.png)

## docker compose

1. Create `.env` file

    ```bash
    # Required

    # https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
    BLOG_WEBHOOKS="webhook1;webhook2"
    TRELLO_WEBHOOKS="webhook1;webhook2"

    # Optional

    # General
    START_DELAY_SECONDS=10
    SLEEP_SECONDS=300

    # Blog
    BLOG_URL="https://www.kineticgames.co.uk/blog"
    BLOG_SITE_INDEX_URL="https://www.kineticgames.co.uk"

    # Trello
    TRELLO_BOARD_ID="9QrnqQ1j"
    TRELLO_API_BASE_URL="https://trello.com/1"
    TRELLO_SHARE_BASE_URL="https://trello.com/b"
    ```

2. Create `docker-compose.yml` file

    ```yml
    services:
    phasmo_update_bot:
        build: .  # or image to private registry
        environment:
        DATABASE_URL: "mysql://root:root@mariadb/phasmo_update_bot"
        env_file:
        - .env
        depends_on:
        - mariadb
        restart: always
    mariadb:
        image: mariadb:latest
        environment:
        MYSQL_ROOT_PASSWORD: root
        MYSQL_DATABASE: phasmo_update_bot
        volumes:
        - ./data/mariadb:/var/lib/mysql
        restart: always
    ```

3. Start with `docker compose up -d`

4. View logs with `docker compose logs --follow`
