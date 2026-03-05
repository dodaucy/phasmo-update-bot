import urllib.parse

import httpx
import pymysql
from bs4 import BeautifulSoup, Tag
from databases import Database
from pydantic import BaseModel

from config import BlogConfig
from webhook_manager import WebhookManager


class BlogItem(BaseModel):
    title: str
    image_url: str
    blog_url: str


_session = httpx.AsyncClient(
    headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"
    }
)


async def _request_blog() -> list[BlogItem]:
    blog_items: list[BlogItem] = []

    # Request blog
    r = await _session.get(BlogConfig.BLOG_URL)
    r.raise_for_status()

    # Parse blog
    soup = BeautifulSoup(r.text, "html.parser")

    # Get blog items
    for article in soup.find_all("a", {"class": "post-preview"}):
        article: Tag

        # check game
        game: str = article.find("div", {"class": "game"}).text.strip().lower()
        if game != "phasmophobia":
            continue

        # Blog item
        blog_items.append(BlogItem(
            title=article.find("div", {"class": "post-title"}).text.strip(),
            image_url=article.find("img", {"class": "post-preview-image"})["src"].strip(),
            blog_url=urllib.parse.urljoin(
                BlogConfig.BLOG_SITE_BASE_URL,
                article["href"].strip()
            )
        ))

    return blog_items


async def check_blog(webhook_managers: list[WebhookManager], db: Database) -> None:
    for blog_item in await _request_blog():
        try:
            await db.execute(
                "INSERT INTO blog_items (blog_url) VALUES (:blog_url)",
                {
                    "blog_url": blog_item.blog_url
                }
            )
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:
                continue
            else:
                raise
        print(f"New blog item: {repr(blog_item.title)}")
        for manager in webhook_managers:
            manager.send({
                "content": None,
                "embeds": [
                    {
                        "title": blog_item.title,
                        "url": blog_item.blog_url,
                        "description": None,
                        "color": 0x08243F,
                        "author": {
                            "name": "Phasmo Blog",
                            "url": BlogConfig.BLOG_URL
                        },
                        "image": {
                            "url": blog_item.image_url
                        }
                    }
                ],
                "username": "Phasmo Blog",
                "avatar_url": "https://cdn.discordapp.com/icons/763935782779879444/a436b678aa2c13cd1edfccee79dc8c5c.png?size=512",
                "attachments": [],
                "flags": 4096
            })
