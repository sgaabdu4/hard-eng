import argparse
import json
import sys
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from . import board, report, state
from .api import Client, Secrets, TrelloError, redact
from .config import (
    OPTIONAL_LISTS,
    REQUIRED_LISTS,
    Config,
    load_config,
    refuse_wall,
    resolve_lists,
)
from .secrets import NAMES, Place, load_secrets, locate, save_secret
from .shapes import Json, Obj, obj, objs, parse_time, stamp, text

WRITE_COMMANDS = ("comment", "move", "label", "upload", "update", "detach", "new")
PROOF_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


@dataclass(frozen=True)
class Session:
    client: Client
    config: Config
    place: Place
    own: str
    run_id: str = ""


def fetch_account(client: Client) -> str:
    return text(
        obj(client.request("GET", "/members/me", {"fields": "username"})).get(
            "username"
        )
    )


def resolve_card(session: Session, ref: str) -> Obj:
    wanted = ref.removeprefix("#")
    found: list[Obj] = []
    for card in board.fetch_cards(session.client, session.config.board):
        number = report.NUMBER.match(text(card.get("name")))
        if wanted == text(card.get("shortLink")) or (
            number and wanted == number.group(1)
        ):
            found.append(card)
    if len(found) > 1:
        links = " and ".join(text(card.get("shortLink")) for card in found)
        raise TrelloError(f"Card {ref} matches two cards: {links}; use a shortLink")
    if not found:
        raise TrelloError(f"Card {ref} is not on the board")
    return found[0]


def log_newest_change(session: Session, card_id: str) -> None:
    if session.client.dry_run:
        return
    rows = objs(
        session.client.request(
            "GET",
            f"/cards/{card_id}/actions",
            {"filter": "createCard,updateCard:idList", "limit": "1"},
        )
    )
    if rows:
        state.log_posted(session.place.state, text(rows[0].get("id")))


def attach(
    session: Session, card_id: str, names: list[str], captions: list[str] | None = None
) -> list[Json]:
    paths = [Path(name) for name in names]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise TrelloError(f"File not found: {', '.join(missing)}")
    rows: list[Json] = []
    for path, caption in zip(paths, captions or [p.name for p in paths], strict=True):
        reply = obj(
            session.client.request(
                "POST",
                f"/cards/{card_id}/attachments",
                {"name": caption},
                [("file", path)],
            )
        )
        url = text(reply.get("url"))
        rows.append(
            {
                "id": text(reply.get("id")),
                "url": url,
                "markdown": f"![{path.name}]({url})",
            }
        )
    return rows


def probe(session: Session, args: argparse.Namespace) -> Obj:
    client, config = session.client, session.config
    info = obj(
        client.request("GET", f"/boards/{config.board}", {"fields": "name,shortLink"})
    )
    lists = board.fetch_names(client, config.board, "lists", "name")
    labels = board.fetch_names(client, config.board, "labels", "name")
    by_name = {name: ident for ident, name in lists.items()}
    rows: list[Json] = [
        {"role": role, "name": name, "id": by_name.get(name, "")}
        for role, name in config.lists.items()
    ]
    payload: Obj = {
        "account": session.own,
        "board": {
            "shortLink": text(info.get("shortLink")),
            "name": text(info.get("name")),
        },
        "lists": rows,
        "labels": [{"id": i, "name": n} for i, n in labels.items() if n],
    }
    if session.own.lower() != config.account.lower():
        payload["error"] = "The token belongs to another account than trello.json names"
    elif any(not obj(row).get("id") for row in rows):
        payload["error"] = "A configured list is missing on the board"
    return payload


def check(session: Session, args: argparse.Namespace) -> Obj:
    started = state.utc_now()
    directory = session.place.state
    saved = state.load_state(directory)
    posted = state.posted_ids(directory)
    snapshot = board.fetch(session.client, session.config, session.own, posted, saved)
    first = (
        text(saved.get("firstCheck")) or text(saved.get("checkedAt")) or stamp(started)
    )
    context = report.Context(
        session.config, snapshot, posted, session.own, started, parse_time(first)
    )
    result: Obj = {field: list(items) for field, items in report.build(context).items()}
    result["runId"] = session.run_id
    state.save_state(
        directory,
        {
            "checkedAt": stamp(started),
            "firstCheck": first,
            "threads": board.threads_to(snapshot.threads),
            "moves": dict(snapshot.moves),
        },
    )
    return result


def comment(session: Session, args: argparse.Namespace) -> Obj:
    try:
        body = Path(args.text_file).read_text()
    except OSError as error:
        raise TrelloError(f"Cannot read {args.text_file}") from error
    for piece in (body, *(Path(name).name for name in args.image)):
        session.config.refuse_private(piece)
    refuse_wall(body)
    found = resolve_card(session, args.card)
    card = text(found.get("id"))
    images = attach(session, card, args.image)
    lines = "\n\n".join(text(obj(row).get("markdown")) for row in images)
    full = body.rstrip() + ("\n\n" + lines if lines else "")
    reply = obj(
        session.client.request(
            "POST", f"/cards/{card}/actions/comments", {"text": full}
        )
    )
    action_id = text(reply.get("id"))
    if action_id:
        state.log_posted(session.place.state, action_id)
    added = add_needs(session, found, body)
    return {"comment": action_id, "attachments": images, "addedLabels": added}


def add_needs(session: Session, card: Obj, body: str) -> list[Json]:
    if not report.QUESTION.search(body):
        return []
    asked = {name.lower() for name in report.TAG.findall(body)}
    wanted = [
        label
        for person, label in session.config.needs.items()
        if person.lower() in asked
    ]
    if not wanted:
        return []
    labels = board.fetch_names(session.client, session.config.board, "labels", "name")
    on_card = card.get("idLabels")
    has = set(on_card) if isinstance(on_card, list) else set[object]()
    added: list[Json] = []
    for name in wanted:
        ident = next((i for i, n in labels.items() if n == name), "")
        if ident and ident not in has:
            session.client.request(
                "POST", f"/cards/{text(card.get('id'))}/idLabels", {"value": ident}
            )
            added.append(name)
    return added


def list_id(session: Session, role: str) -> str:
    list_name = session.config.lists.get(role)
    if not list_name:
        raise TrelloError(f"No list is configured for {role}")
    names = board.fetch_names(session.client, session.config.board, "lists", "name")
    lists = {name: ident for ident, name in names.items()}
    if list_name not in lists:
        raise TrelloError(f"The list {list_name} is missing on the board")
    return lists[list_name]


def next_number(session: Session) -> int:
    cards = objs(
        session.client.request(
            "GET", f"/boards/{session.config.board}/cards/all", {"fields": "name"}
        )
    )
    numbers = [
        int(found.group(1))
        for card in cards
        if (found := report.NUMBER.match(text(card.get("name"))))
    ]
    return max(numbers, default=0) + 1


def new(session: Session, args: argparse.Namespace) -> Obj:
    client, config = session.client, session.config
    title = report.NUMBER.sub("", args.title).strip()
    try:
        details = (
            Path(args.description_file).read_text() if args.description_file else ""
        )
    except OSError as error:
        raise TrelloError("The description file could not be read") from error
    for piece in (title, details):
        config.refuse_private(piece)
    refuse_wall(details)
    target = list_id(session, args.role)
    number = next_number(session)
    made = obj(
        client.request(
            "POST",
            "/cards",
            {
                "idList": target,
                "name": f"#{number} {title}",
                "pos": "top",
                "desc": details,
            },
        )
    )
    log_newest_change(session, text(made.get("id")))
    return {"card": number, "url": text(made.get("shortUrl"))}


def move(session: Session, args: argparse.Namespace) -> Obj:
    client = session.client
    if args.role == "testing" and not args.proof:
        raise TrelloError("A move to testing needs at least one --proof image")
    if (args.role == "testing" or args.shows) and len(args.shows) != len(args.proof):
        raise TrelloError("Give one --shows per --proof: the change each image shows")
    not_images = [n for n in args.proof if Path(n).suffix.lower() not in PROOF_SUFFIXES]
    if not_images:
        raise TrelloError(f"Proof must be {', '.join(PROOF_SUFFIXES)}: {not_images}")
    for caption in args.shows:
        session.config.refuse_private(caption)
    card = resolve_card(session, args.card)
    target = list_id(session, args.role)
    card_id = text(card.get("id"))
    proofs = attach(session, card_id, args.proof, args.shows or None)
    client.request("PUT", f"/cards/{card_id}", {"idList": target, "pos": "top"})
    log_newest_change(session, card_id)
    removed = clear_needs(session, card) if args.role == "done" else list[Json]()
    return {"moved": args.role, "attachments": proofs, "removedLabels": removed}


def clear_needs(session: Session, card: Obj) -> list[Json]:
    labels = board.fetch_names(session.client, session.config.board, "labels", "name")
    on_card = card.get("idLabels")
    removed: list[Json] = []
    for ident in on_card if isinstance(on_card, list) else []:
        name = labels.get(text(ident), "")
        if name in session.config.needs.values():
            session.client.request(
                "DELETE", f"/cards/{text(card.get('id'))}/idLabels/{text(ident)}"
            )
            removed.append(name)
    return removed


def label(session: Session, args: argparse.Namespace) -> Obj:
    card = resolve_card(session, args.card)
    labels = board.fetch_names(session.client, session.config.board, "labels", "name")
    ident = next((i for i, name in labels.items() if name == args.label), "")
    if not ident and args.label == report.REAL_CASE and args.action == "add":
        made = session.client.request(
            "POST",
            f"/boards/{session.config.board}/labels",
            {"name": args.label, "color": "green"},
        )
        ident = text(obj(made).get("id")) or "new-label"
    if not ident:
        raise TrelloError(f"The board has no label named {args.label}")
    on_card = card.get("idLabels")
    has = isinstance(on_card, list) and ident in on_card
    adding = args.action == "add"
    if has == adding:
        return {"unchanged": True}
    card_id = text(card.get("id"))
    if adding:
        session.client.request("POST", f"/cards/{card_id}/idLabels", {"value": ident})
    else:
        session.client.request("DELETE", f"/cards/{card_id}/idLabels/{ident}")
    return {"label": args.label, "action": args.action}


def upload(session: Session, args: argparse.Namespace) -> Obj:
    card = text(resolve_card(session, args.card).get("id"))
    return {"attachments": attach(session, card, args.paths)}


def detach(session: Session, args: argparse.Namespace) -> Obj:
    card = text(resolve_card(session, args.card).get("id"))
    for ident in args.ids:
        session.client.request("DELETE", f"/cards/{card}/attachments/{ident}")
    return {"detached": list(args.ids)}


def update(session: Session, args: argparse.Namespace) -> Obj:
    changes: dict[str, str] = {}
    if args.name:
        changes["name"] = args.name
    if args.due:
        try:
            parse_time(args.due)
        except ValueError as error:
            raise TrelloError("--due must be an ISO date and time") from error
        changes["due"] = args.due
    if not changes and not args.renumber:
        raise TrelloError("update needs --name, --due or --renumber")
    found = resolve_card(session, args.card)
    if args.renumber:
        title = report.NUMBER.sub("", args.name or text(found.get("name"))).strip()
        changes["name"] = f"#{next_number(session)} {title}"
    card = text(found.get("id"))
    session.client.request("PUT", f"/cards/{card}", changes)
    return {"updated": list[Json](sorted(changes))}


def comment_rows(actions: list[Obj], members: dict[str, str]) -> list[Json]:
    ordered = sorted(actions, key=lambda a: parse_time(text(a.get("date"))))
    rows: list[Json] = []
    for action in ordered:
        who = text(action.get("idMemberCreator"))
        data = obj(action.get("data"))
        rows.append(
            {
                "author": members.get(who, who),
                "date": text(action.get("date")),
                "text": text(data.get("text")),
            }
        )
    return rows


def card(session: Session, args: argparse.Namespace) -> Obj:
    client, board_id = session.client, session.config.board
    card_id = text(resolve_card(session, args.card).get("id"))
    detail = obj(
        client.request(
            "GET", f"/cards/{card_id}", {"fields": "name,desc,due,idList,idLabels"}
        )
    )
    lists = board.fetch_names(client, board_id, "lists", "name")
    labels = board.fetch_names(client, board_id, "labels", "name")
    members = board.fetch_names(client, board_id, "members", "username")
    actions = board.paged(
        client, f"/cards/{card_id}/actions", {"filter": "commentCard"}
    )
    files = objs(
        client.request(
            "GET", f"/cards/{card_id}/attachments", {"fields": "id,name,url,date"}
        )
    )
    ids = detail.get("idLabels")
    return {
        "name": text(detail.get("name")),
        "list": lists.get(text(detail.get("idList")), ""),
        "labels": [labels.get(text(i), "") for i in ids]
        if isinstance(ids, list)
        else [],
        "due": detail.get("due"),
        "description": text(detail.get("desc")),
        "comments": comment_rows(actions, members),
        "attachments": [
            {key: f.get(key) for key in ("id", "name", "url", "date")} for f in files
        ],
    }


def download(session: Session, args: argparse.Namespace) -> Obj:
    card = text(resolve_card(session, args.card).get("id"))
    since = parse_time(args.since) if args.since else None
    folder = Path(args.dir) if args.dir else session.place.state / "downloads"
    rows = objs(
        session.client.request(
            "GET", f"/cards/{card}/attachments", {"fields": "name,date,isUpload"}
        )
    )
    saved: list[Json] = []
    for row in rows:
        if row.get("isUpload") is not True or (
            since and parse_time(text(row.get("date"))) < since
        ):
            continue
        ident, name = text(row.get("id")), Path(text(row.get("name"))).name
        data = session.client.download(
            f"/cards/{card}/attachments/{ident}/download/{urllib.parse.quote(name)}"
        )
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{ident}-{name}"
        target.write_bytes(data)
        saved.append(str(target))
    return {"paths": saved}


HANDLERS: dict[str, Callable[[Session, argparse.Namespace], Obj]] = {
    "probe": probe,
    "new": new,
    "check": check,
    "comment": comment,
    "move": move,
    "label": label,
    "card": card,
    "update": update,
    "upload": upload,
    "detach": detach,
    "download": download,
}


def build_parser() -> tuple[
    argparse.ArgumentParser, dict[str, argparse.ArgumentParser]
]:
    parser = argparse.ArgumentParser(prog="trello.py")
    commands = parser.add_subparsers(dest="command", required=True)
    dry = argparse.ArgumentParser(add_help=False)
    dry.add_argument("--dry-run", action="store_true")
    subs: dict[str, argparse.ArgumentParser] = {}
    for name in ("probe", "check", "finish"):
        subs[name] = commands.add_parser(name)
    for name in WRITE_COMMANDS:
        subs[name] = commands.add_parser(name, parents=[dry])
    for name in ("card", "download"):
        subs[name] = commands.add_parser(name)
    subs["finish"].add_argument("run_id")
    subs["save-secret"] = commands.add_parser("save-secret")
    subs["save-secret"].add_argument("name", choices=NAMES)
    subs["save-secret"].add_argument("file")
    for name in (
        "comment",
        "move",
        "label",
        "upload",
        "download",
        "card",
        "update",
        "detach",
    ):
        subs[name].add_argument("card")
    subs["comment"].add_argument("text_file")
    subs["comment"].add_argument("--image", nargs="+", action="extend", default=[])
    subs["move"].add_argument("role", choices=[*REQUIRED_LISTS, *OPTIONAL_LISTS])
    subs["new"].add_argument("role", choices=[*REQUIRED_LISTS, *OPTIONAL_LISTS])
    subs["new"].add_argument("title")
    subs["new"].add_argument("--description-file")
    subs["move"].add_argument("--proof", nargs="+", action="extend", default=[])
    subs["move"].add_argument("--shows", action="append", default=[])
    subs["label"].add_argument("action", choices=["add", "remove"])
    subs["label"].add_argument("label")
    subs["upload"].add_argument("paths", nargs="+")
    subs["detach"].add_argument("ids", nargs="+")
    subs["update"].add_argument("--name")
    subs["update"].add_argument("--due")
    subs["update"].add_argument("--renumber", action="store_true")
    subs["download"].add_argument("--since")
    subs["download"].add_argument("--dir")
    return parser, subs


def run_command(
    args: argparse.Namespace,
    place: Place,
    secrets: Secrets,
    config: Config,
    run_id: str,
) -> Obj:
    dry_run = bool(vars(args).get("dry_run", False))
    client = Client(secrets, dry_run=dry_run)
    own = fetch_account(client)
    config = replace(config, account=config.account or own)
    if not config.lists:
        names = board.fetch_names(client, config.board, "lists", "name").values()
        config = resolve_lists(config, names)
    if args.command != "probe" and own.lower() != config.account.lower():
        raise TrelloError("The token belongs to another account than trello.json names")
    session = Session(client, config, place, own, run_id)
    payload = HANDLERS[args.command](session, args)
    return {"dryRun": client.planned} if dry_run else payload


def guarded(args: argparse.Namespace, place: Place, secrets: Secrets) -> Obj:
    config = load_config(place.root)
    if args.command == "finish":
        return {"finished": state.end_lease(place.state, args.run_id)}
    if args.command != "check":
        return run_command(args, place, secrets, config, "")
    run_id = state.take_lease(place.state, config.every_minutes)
    if run_id is None:
        return {"skipped": True}
    try:
        return run_command(args, place, secrets, config, run_id)
    except TrelloError:
        state.end_lease(place.state, run_id)
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser()[0].parse_args(argv)
    secrets = Secrets("", "")
    try:
        place = locate(Path.cwd())
        if args.command == "save-secret":
            payload = {"saved": save_secret(place, args.name, Path(args.file))}
        else:
            secrets = load_secrets(place.main)
            payload = guarded(args, place, secrets)
    except TrelloError as error:
        payload = {"error": str(error)}
    sys.stdout.write(
        redact(json.dumps(payload, indent=2, ensure_ascii=False), secrets) + "\n"
    )
    return 1 if "error" in payload else 0
