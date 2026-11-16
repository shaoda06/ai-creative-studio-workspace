"""Page Chloe asset cards after filtering their catalog records."""
from dataclasses import dataclass
from functools import partial
from typing import Annotated, Callable

from fastapi import Query, Request

from backend.services.read_views import view_response, views
from project_resources import reuse_read_indexes


class AssetPage:
    def __init__(
        self,
        page: Annotated[int | None, Query(ge=1)] = None,
        page_size: Annotated[int, Query(ge=1, le=60)] = 12,
        available: bool = False,
        require_media: bool = False,
        form: str = '',
        types: Annotated[list[str] | None, Query()] = None,
        ids: Annotated[list[str] | None, Query()] = None,
        models: Annotated[list[str] | None, Query()] = None,
    ):
        self.page = page
        self.page_size = page_size
        self.available = available
        self.require_media = require_media
        self.form = form
        self.types = set(types or ())
        self.ids = ids
        self.models = set(models or ())


@dataclass
class AssetRow:
    id: str
    card: Callable[[], dict]
    status: str = ''
    has_media: bool = False
    form: str | None = None
    type: str | None = None
    models: tuple = ()
    types: tuple[str, ...] = ()

    @property
    def filter_types(self):
        return self.types or ((self.type,) if self.type else ())


def respond_asset_page(request: Request, space, endpoint, options: AssetPage, build, *, folders, scope=None):
    rows, revision = views.read((space.api, endpoint, scope), folders, build)
    return view_response(request, revision, partial(asset_page, rows, options))


def asset_page(rows, options: AssetPage):
    eligible = [
        row for row in rows
        if (not options.available or row.status == '可用')
        and (not options.require_media or row.has_media)
        and (not options.models or options.models.intersection(row.models))
        and (not options.form or (row.form == '套装') == (options.form == '套装'))
        and (options.form != '单件' or not options.available or row.form == '单件')
    ]
    with reuse_read_indexes():
        if options.ids is not None:
            by_id = {row.id: row for row in eligible}
            return [by_id[key].card() for key in options.ids if key in by_id]
        filtered = [row for row in eligible if not options.types or options.types.intersection(row.filter_types)]
        if options.page is None:
            return [row.card() for row in filtered]
        types = sorted({kind for row in eligible for kind in row.filter_types})
        total = len(filtered)
        size = options.page_size
        page = min(options.page, max(1, (total + size - 1) // size))
        start = (page - 1) * size
        return {'items': [row.card() for row in filtered[start:start + size]],
                'total': total, 'page': page, 'page_size': size, 'types': types}
