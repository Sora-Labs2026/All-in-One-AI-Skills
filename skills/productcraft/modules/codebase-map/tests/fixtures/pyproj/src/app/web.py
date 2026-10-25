from fastapi import APIRouter
from flask import Blueprint

router = APIRouter()
bp = Blueprint("auth", __name__)


@router.get("/items/{item_id}")
def read_item(item_id: int):
    return {"id": item_id}


@bp.route("/login", methods=["POST"])
def login():
    return "ok"


@bp.route("/logout")
def logout():
    return "bye"


def not_a_route(client):
    return client.get("/elsewhere")
