import asyncio

from databases import Database

from blog import check_blog
from config import (BLOG_WEBHOOKS, DATABASE, SLEEP_SECONDS,
                    START_DELAY_SECONDS, TRELLO_WEBHOOKS)
from trello import check_trello
from webhook_manager import WebhookManager


class PhasmoUpdateBot:
    def __init__(self) -> None:
        # Database
        self._db = Database(DATABASE)

        # Webhook managers
        self._blog_webhook_managers: list[WebhookManager] = []
        self._trello_webhook_managers: list[WebhookManager] = []
        for webhook_url in BLOG_WEBHOOKS:
            self._blog_webhook_managers.append(WebhookManager(webhook_url))
        for webhook_url in TRELLO_WEBHOOKS:
            self._trello_webhook_managers.append(WebhookManager(webhook_url))

    async def main(self) -> None:
        print("Wait for start...")
        await asyncio.sleep(START_DELAY_SECONDS)

        print("Connect to database...")
        await self._db.connect()

        print("Create database tables...")
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS blog_items (
                blog_url VARCHAR(255) NOT NULL PRIMARY KEY
            )
            """
        )
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS trello_lists (
                list_id VARCHAR(255) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            )
            """
        )
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS trello_items (
                list_id VARCHAR(255) NOT NULL,
                FOREIGN KEY (list_id) REFERENCES trello_lists(list_id),
                item_id VARCHAR(255) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                labels VARCHAR(255) NOT NULL
            )
            """
        )

        print("Running")
        while True:
            # Trello
            if len(self._trello_webhook_managers) > 0:
                print("Check for trello updates...")
                await check_trello(self._trello_webhook_managers, self._db)
            else:
                print("No trello webhooks configured")

            # Blog
            if len(self._blog_webhook_managers) > 0:
                print("Check for blog updates...")
                await check_blog(self._blog_webhook_managers, self._db)
            else:
                print("No blog webhooks configured")

            # Sleep
            print("Done, sleeping...")
            await asyncio.sleep(SLEEP_SECONDS)

    async def run(self) -> None:
        await asyncio.gather(
            self.main(),
            *[manager.run() for manager in self._blog_webhook_managers],
            *[manager.run() for manager in self._trello_webhook_managers]
        )


bot = PhasmoUpdateBot()

asyncio.run(bot.run())
