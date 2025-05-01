import json

import httpx
import pymysql
from databases import Database
from pydantic import BaseModel

from config import TrelloConfig
from webhook_manager import WebhookManager


class TrelloListItem(BaseModel):
    list_id: str
    item_id: str
    name: str
    desc: str | None
    labels: list[str]
    url: str | None


class TrelloList(BaseModel):
    list_id: str
    name: str
    items: list[TrelloListItem]


_session = httpx.AsyncClient(
    headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"
    }
)

AUTHOR = {
    "name": "Phasmo Trello",
    "url": f"{TrelloConfig.TRELLO_SHARE_BASE_URL}/{TrelloConfig.TRELLO_BOARD_ID}"
}
USERNAME = "Phasmo Trello"
AVATAR_URL = "https://user-images.githubusercontent.com/13432607/29981988-82cec158-8f58-11e7-9f26-473079c2a9b1.png"
ATTACHMENTS = []
FLAGS = 4096


async def _request_trello_lists() -> list[TrelloList]:
    trello_lists: list[TrelloList] = []

    # Request trello
    r = await _session.get(
        f"{TrelloConfig.TRELLO_API_BASE_URL}/board/{TrelloConfig.TRELLO_BOARD_ID}",
        params={  # Original params to avoid bot detection
            "fields": "id",
            "cards": "visible",
            "card_fields": "id,address,badges,cardRole,closed,coordinates,cover,creationMethod,creationMethodError,creationMethodLoadingStartedAt,dateLastActivity,desc,descData,due,dueComplete,dueReminder,idAttachmentCover,idBoard,idLabels,idList,idMembers,idShort,isTemplate,labels,limits,locationName,mirrorSourceId,name,nodeId,pinned,pos,shortLink,shortUrl,start,subscribed,url",
            "card_attachments": "true",
            "card_attachment_fields": "id,bytes,date,edgeColor,fileName,idMember,isMalicious,isUpload,mimeType,name,pos,url",
            "card_checklists": "all",
            "card_checklist_fields": "id,idBoard,idCard,name,pos",
            "card_checklist_checkItems": "none",
            "card_customFieldItems": "true",
            "card_pluginData": "true",
            "card_stickers": "true",
            "lists": "open",
            "list_fields": "id,closed,color,creationMethod,datasource,idBoard,limits,name,pos,softLimit,subscribed,type",
        }
    )
    r.raise_for_status()
    json_response = r.json()

    # Parse trello
    for list_ in json_response["lists"]:
        list_: dict

        # Search matching items
        items: list[TrelloListItem] = []
        for card in json_response["cards"]:
            card: dict

            # Skip if not in list
            if card["idList"] != list_["id"]:
                continue

            # Description
            desc: str = card["desc"]
            for checklist in card["checklists"]:
                print(f"Request checklist {checklist['id']}")
                r = await _session.get(  # Original params to avoid bot detection
                    f"{TrelloConfig.TRELLO_API_BASE_URL}/checklists/{checklist['id']}",
                    params={
                        "fields": "id,name,pos",
                        "checkItems": "all",
                        "checkItem_fields": "id,due,dueReminder,idChecklist,idMember,name,nameData,pos,state,temporaryId"
                    }
                )
                r.raise_for_status()
                checklist_response = r.json()
                desc += f"\n\n{checklist_response['name']}:"
                for check_item in sorted(checklist_response["checkItems"], key=lambda item: item["pos"]):
                    desc += f"\n- {check_item['name']}: {check_item['state'].lower()}"
            desc = desc.strip()

            # Get item
            item = TrelloListItem(
                list_id=card["idList"],
                item_id=card["id"],
                name=card["name"],
                desc=desc or None,
                labels=[label["name"] for label in card["labels"]],
                url=card["shortUrl"]
            )
            items.append(item)

        # Create trello list
        trello_list = TrelloList(
            list_id=list_["id"],
            name=list_["name"],
            items=items
        )
        trello_lists.append(trello_list)

    return trello_lists


async def _get_existing_trello_lists(db: Database) -> list[TrelloList]:
    fetched_existing_trello_lists = await db.fetch_all(
        "SELECT * FROM trello_lists"
    )
    fetched_existing_trello_items = await db.fetch_all(
        "SELECT * FROM trello_items"
    )

    existing_trello_lists: list[TrelloList] = []
    for trello_list in fetched_existing_trello_lists:
        trello_items: list[TrelloListItem] = []
        for trello_item in fetched_existing_trello_items:
            if trello_item["list_id"] == trello_list["list_id"]:
                trello_items.append(
                    TrelloListItem(
                        list_id=trello_item["list_id"],
                        item_id=trello_item["item_id"],
                        name=trello_item["name"],
                        desc=trello_item["description"],
                        labels=json.loads(trello_item["labels"]),
                        url=None
                    )
                )
        existing_trello_lists.append(
            TrelloList(
                list_id=trello_list["list_id"],
                name=trello_list["name"],
                items=trello_items
            )
        )

    return existing_trello_lists


async def check_trello(webhook_managers: list[WebhookManager], db: Database) -> None:
    # Request trello
    trello_lists = await _request_trello_lists()

    # Get existing trello lists
    existing_trello_lists = await _get_existing_trello_lists(db)

    # Check for new trello lists
    for trello_list in trello_lists:
        found = False
        for existing_trello_list in existing_trello_lists:
            if trello_list.list_id == existing_trello_list.list_id:
                found = True
                break
        if not found:
            print(f"New trello list: {repr(trello_list.name)}")
            for manager in webhook_managers:
                manager.send({
                    "content": None,
                    "embeds": [
                        {
                            "title": f"New list: {trello_list.name}",
                            "color": 0xb50ffc,
                            "author": AUTHOR
                        }
                    ],
                    "username": USERNAME,
                    "avatar_url": AVATAR_URL,
                    "attachments": ATTACHMENTS,
                    "flags": FLAGS
                })
            await db.execute(
                "INSERT INTO trello_lists (list_id, name) VALUES (:list_id, :name)",
                {
                    "list_id": trello_list.list_id,
                    "name": trello_list.name
                }
            )

    # Check for renamed or deleted trello lists
    for existing_trello_list in existing_trello_lists:
        trello_list = None
        for list_ in trello_lists:
            if list_.list_id == existing_trello_list.list_id:
                trello_list = list_
                break
        if trello_list is not None:  # Check if renamed
            if existing_trello_list.name != trello_list.name:
                print(f"Renamed trello list: {repr(existing_trello_list.name)} -> {repr(trello_list.name)}")
                for manager in webhook_managers:
                    manager.send({
                        "content": None,
                        "embeds": [
                            {
                                "title": f"Renamed list: {trello_list.name}",
                                "fields": [
                                    {
                                        "name": "Old name",
                                        "value": existing_trello_list.name,
                                        "inline": True
                                    },
                                    {
                                        "name": "New name",
                                        "value": trello_list.name,
                                        "inline": True
                                    }
                                ],
                                "color": 0xb50ffc,
                                "author": AUTHOR
                            }
                        ],
                        "username": USERNAME,
                        "avatar_url": AVATAR_URL,
                        "attachments": ATTACHMENTS,
                        "flags": FLAGS
                    })
                await db.execute(
                    "UPDATE trello_lists SET name = :name WHERE list_id = :list_id",
                    {
                        "name": trello_list.name,
                        "list_id": existing_trello_list.list_id
                    }
                )
        else:  # Deleted
            print(f"Deleted trello list: {repr(existing_trello_list.name)}")
            for manager in webhook_managers:
                manager.send({
                    "content": None,
                    "embeds": [
                        {
                            "title": f"Deleted list: {existing_trello_list.name}",
                            "color": 0xb50ffc,
                            "author": AUTHOR
                        }
                    ],
                    "username": USERNAME,
                    "avatar_url": AVATAR_URL,
                    "attachments": ATTACHMENTS,
                    "flags": FLAGS
                })
            await db.execute(
                "DELETE FROM trello_lists WHERE list_id = :list_id",
                {
                    "list_id": existing_trello_list.list_id
                }
            )
            await db.execute(
                "DELETE FROM trello_items WHERE list_id = :list_id",
                {
                    "list_id": existing_trello_list.list_id
                }
            )

    # Check for new trello items
    for trello_list in trello_lists:
        for item in trello_list.items:
            found = False
            for existing_trello_list in existing_trello_lists:
                for existing_trello_item in existing_trello_list.items:
                    if item.item_id == existing_trello_item.item_id:
                        found = True
                        break
                if found:
                    break
            if not found:
                print(f"New trello item: {repr(item.name)}")
                for manager in webhook_managers:
                    manager.send({
                        "content": None,
                        "embeds": [
                            {
                                "title": f"Created in {trello_list.name}: {item.name}",
                                "url": item.url,
                                "description": item.desc or "*No description*",
                                "color": 0x15d60e,
                                "author": AUTHOR,
                                "footer": {
                                    "text": f"Labels: {', '.join(item.labels) or 'None'}"
                                }
                            }
                        ],
                        "username": USERNAME,
                        "avatar_url": AVATAR_URL,
                        "attachments": ATTACHMENTS,
                        "flags": FLAGS
                    })
                await db.execute(
                    "INSERT INTO trello_items (list_id, item_id, name, description, labels) VALUES (:list_id, :item_id, :name, :desc, :labels)",
                    {
                        "list_id": item.list_id,
                        "item_id": item.item_id,
                        "name": item.name,
                        "desc": item.desc,
                        "labels": json.dumps(item.labels)
                    }
                )

    # Check for changed or deleted trello items
    for existing_trello_list in existing_trello_lists:
        for existing_trello_item in existing_trello_list.items:
            trello_item = None
            for list_ in trello_lists:
                for item in list_.items:
                    if item.item_id == existing_trello_item.item_id:
                        trello_item = item
                        break
                if trello_item is not None:
                    break
            if trello_item is not None:  # Check if changed
                if existing_trello_item.name != trello_item.name:  # Check if renamed
                    print(f"Changed trello item name: {repr(existing_trello_item.name)} -> {repr(trello_item.name)}")
                    for manager in webhook_managers:
                        manager.send({
                            "content": None,
                            "embeds": [
                                {
                                    "title": f"Changed name: {trello_item.name}",
                                    "fields": [
                                        {
                                            "name": "Old name",
                                            "value": existing_trello_item.name,
                                            "inline": True
                                        },
                                        {
                                            "name": "New name",
                                            "value": trello_item.name,
                                            "inline": True
                                        }
                                    ],
                                    "url": trello_item.url,
                                    "color": 0xfcf80f,
                                    "author": AUTHOR,
                                    "footer": {
                                        "text": f"Labels: {', '.join(trello_item.labels) or 'None'}"
                                    }
                                }
                            ],
                            "username": USERNAME,
                            "avatar_url": AVATAR_URL,
                            "attachments": ATTACHMENTS,
                            "flags": FLAGS
                        })
                    await db.execute(
                        "UPDATE trello_items SET name = :name WHERE item_id = :item_id",
                        {
                            "name": trello_item.name,
                            "item_id": trello_item.item_id
                        }
                    )
                if existing_trello_item.desc != trello_item.desc:  # Check if description changed
                    print(f"Changed trello item description from {repr(trello_item.name)}")
                    old_desc = existing_trello_item.desc or "*No description*"
                    if len(old_desc) > 512:
                        old_desc = f"{old_desc[:508]}\n..."
                    new_desc = trello_item.desc or "*No description*"
                    if len(new_desc) > 512:
                        new_desc = f"{new_desc[:508]}\n..."
                    for manager in webhook_managers:
                        manager.send({
                            "content": None,
                            "embeds": [
                                {
                                    "title": f"Changed description: {trello_item.name}",
                                    "url": trello_item.url,
                                    "fields": [
                                        {
                                            "name": "Old description",
                                            "value": old_desc,
                                            "inline": True
                                        },
                                        {
                                            "name": "New description",
                                            "value": new_desc,
                                            "inline": True
                                        }
                                    ],
                                    "color": 0xfcf80f,
                                    "author": AUTHOR,
                                    "footer": {
                                        "text": f"Labels: {', '.join(trello_item.labels) or 'None'}"
                                    }
                                }
                            ],
                            "username": USERNAME,
                            "avatar_url": AVATAR_URL,
                            "attachments": ATTACHMENTS,
                            "flags": FLAGS
                        })
                    await db.execute(
                        "UPDATE trello_items SET description = :desc WHERE item_id = :item_id",
                        {
                            "desc": trello_item.desc,
                            "item_id": trello_item.item_id
                        }
                    )
                if existing_trello_item.labels != trello_item.labels:  # Check if labels changed
                    print(f"Changed trello item labels from {repr(trello_item.name)}")
                    for manager in webhook_managers:
                        manager.send({
                            "content": None,
                            "embeds": [
                                {
                                    "title": f"Changed labels: {trello_item.name}",
                                    "url": trello_item.url,
                                    "fields": [
                                        {
                                            "name": "Old labels",
                                            "value": ", ".join(existing_trello_item.labels),
                                            "inline": True
                                        },
                                        {
                                            "name": "New labels",
                                            "value": ", ".join(trello_item.labels),
                                            "inline": True
                                        }
                                    ],
                                    "color": 0xfcf80f,
                                    "author": AUTHOR
                                }
                            ],
                            "username": USERNAME,
                            "avatar_url": AVATAR_URL,
                            "attachments": ATTACHMENTS,
                            "flags": FLAGS
                        })
                    await db.execute(
                        "UPDATE trello_items SET labels = :labels WHERE item_id = :item_id",
                        {
                            "labels": json.dumps(trello_item.labels),
                            "item_id": trello_item.item_id
                        }
                    )
                if existing_trello_item.list_id != trello_item.list_id:  # Check if moved
                    print(f"Moved trello item: {repr(trello_item.name)}")
                    # Get old and new list names
                    old_list_name = None
                    for list_ in trello_lists:
                        if list_.list_id == existing_trello_item.list_id:
                            old_list_name = list_.name
                            break
                    if old_list_name is None:
                        raise Exception("Old list name not found")
                    new_list_name = None
                    for list_ in trello_lists:
                        if list_.list_id == trello_item.list_id:
                            new_list_name = list_.name
                            break
                    if new_list_name is None:
                        raise Exception("New list name not found")
                    # Send webhook
                    for manager in webhook_managers:
                        manager.send({
                            "content": None,
                            "embeds": [
                                {
                                    "title": f"Moved: {trello_item.name}",
                                    "url": trello_item.url,
                                    "fields": [
                                        {
                                            "name": "Old list",
                                            "value": old_list_name,
                                            "inline": True
                                        },
                                        {
                                            "name": "New list",
                                            "value": new_list_name,
                                            "inline": True
                                        }
                                    ],
                                    "color": 0xfcf80f,
                                    "author": AUTHOR,
                                    "footer": {
                                        "text": f"Labels: {', '.join(trello_item.labels) or 'None'}"
                                    }
                                }
                            ],
                            "username": USERNAME,
                            "avatar_url": AVATAR_URL,
                            "attachments": ATTACHMENTS,
                            "flags": FLAGS
                        })
                    # Update database
                    await db.execute(
                        "UPDATE trello_items SET list_id = :list_id WHERE item_id = :item_id",
                        {
                            "list_id": trello_item.list_id,
                            "item_id": trello_item.item_id
                        }
                    )
            else:  # Deleted
                print(f"Deleted trello item: {repr(existing_trello_item.name)}")
                for manager in webhook_managers:
                    manager.send({
                        "content": None,
                        "embeds": [
                            {
                                "title": f"Deleted: {existing_trello_item.name}",
                                "color": 0xfc0f17,
                                "author": AUTHOR,
                                "footer": {
                                    "text": f"Labels: {', '.join(existing_trello_item.labels) or 'None'}"
                                }
                            }
                        ],
                        "username": USERNAME,
                        "avatar_url": AVATAR_URL,
                        "attachments": ATTACHMENTS,
                        "flags": FLAGS
                    })
                await db.execute(
                    "DELETE FROM trello_items WHERE item_id = :item_id",
                    {
                        "item_id": existing_trello_item.item_id
                    }
                )
