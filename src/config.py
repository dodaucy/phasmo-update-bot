import os

from dotenv import load_dotenv


load_dotenv(".env")


BLOG_WEBHOOKS = os.environ["BLOG_WEBHOOKS"].split(";")
TRELLO_WEBHOOKS = os.environ["TRELLO_WEBHOOKS"].split(";")

DATABASE = os.environ["DATABASE_URL"]

START_DELAY_SECONDS = float(os.environ.get("START_DELAY_SECONDS", 10))
SLEEP_SECONDS = float(os.environ.get("SLEEP_SECONDS", 60 * 5))


class BlogConfig:
    BLOG_URL = os.environ.get("BLOG_URL", "https://www.kineticgames.co.uk/blog")
    BLOG_SITE_INDEX_URL = os.environ.get("BLOG_SITE_INDEX_URL", "https://www.kineticgames.co.uk")


class TrelloConfig:
    TRELLO_BOARD_ID = os.environ.get("TRELLO_BOARD_ID", "9QrnqQ1j")
    TRELLO_API_BASE_URL = os.environ.get("TRELLO_BASE_URL", "https://trello.com/1")
    TRELLO_SHARE_BASE_URL = os.environ.get("TRELLO_SHARE_URL", "https://trello.com/b")
