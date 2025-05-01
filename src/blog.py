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
    excerpt: str | None


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
    for article in soup.find_all("article", {"class": "blog-item"}):
        article: Tag

        # Summary
        summary_tag: Tag | None = article.find("section", {"class": "blog-item-summary"})
        if summary_tag is None:
            raise Exception("Summary not found")

        # Excerpt
        excerpt_tag: Tag | None = summary_tag.find("div", {"class": "blog-excerpt"})
        if excerpt_tag is not None and excerpt_tag.text.strip() != "":
            excerpt = excerpt_tag.text.strip()
        else:
            excerpt = None

        # Image wrapper
        image_wrapper: Tag | None = article.find("section", {"class": "blog-image-wrapper"})
        if image_wrapper is None:
            raise Exception("Image wrapper not found")

        # Blog item
        blog_items.append(BlogItem(
            title=summary_tag.find("h1", {"class": "blog-title"}).text.strip(),
            image_url=image_wrapper.find("img")["src"].strip(),
            blog_url=urllib.parse.urljoin(
                BlogConfig.BLOG_SITE_INDEX_URL,
                summary_tag.find("a", {"class": "blog-more-link"})["href"].strip()
            ),
            excerpt=excerpt
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
                        "description": blog_item.excerpt,
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
