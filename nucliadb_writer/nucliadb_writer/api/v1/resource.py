# Copyright (C) 2021 Bosutech XXI S.L.
#
# nucliadb is offered under the AGPL v3.0 and as commercial software.
# For commercial licensing, contact us at info@nuclia.com.
#
# AGPL:
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import HTTPException, Response
from fastapi.params import Header
from fastapi_versioning import version  # type: ignore
from nucliadb_protos.writer_pb2 import BrokerMessage, IndexResource
from starlette.requests import Request

from nucliadb_ingest.orm.knowledgebox import KnowledgeBox
from nucliadb_ingest.processing import PushPayload, Source
from nucliadb_ingest.utils import get_driver
from nucliadb_models.resource import NucliaDBRoles
from nucliadb_telemetry.utils import set_info_on_span
from nucliadb_utils.authentication import requires
from nucliadb_utils.exceptions import LimitsExceededError
from nucliadb_utils.utilities import (
    get_cache,
    get_ingest,
    get_partitioning,
    get_storage,
    get_transaction,
)
from nucliadb_writer import SERVICE_NAME
from nucliadb_writer.api.models import (
    CreateResourcePayload,
    ResourceCreated,
    ResourceUpdated,
    UpdateResourcePayload,
)
from nucliadb_writer.api.v1.router import (
    KB_PREFIX,
    RESOURCE_PREFIX,
    RESOURCES_PREFIX,
    api,
)
from nucliadb_writer.resource.audit import parse_audit
from nucliadb_writer.resource.basic import (
    parse_basic,
    parse_basic_modify,
    set_status,
    set_status_modify,
)
from nucliadb_writer.resource.field import extract_fields, parse_fields
from nucliadb_writer.resource.origin import parse_origin
from nucliadb_writer.utilities import get_processing

if TYPE_CHECKING:
    SKIP_STORE_DEFAULT = False
else:
    SKIP_STORE_DEFAULT = Header(False)


@api.post(
    f"/{KB_PREFIX}/{{kbid}}/{RESOURCES_PREFIX}",
    status_code=201,
    name="Create Resource",
    response_model=ResourceCreated,
    tags=["Resources"],
)
@requires(NucliaDBRoles.WRITER)
@version(1)
async def create_resource(
    request: Request,
    item: CreateResourcePayload,
    kbid: str,
    x_skip_store: bool = SKIP_STORE_DEFAULT,
):
    transaction = get_transaction()
    processing = get_processing()
    partitioning = get_partitioning()

    # Create resource message
    uuid = uuid4().hex
    partition = partitioning.generate_partition(kbid, uuid)

    writer = BrokerMessage()
    toprocess = PushPayload(
        uuid=uuid,
        kbid=kbid,
        partition=partition,
        userid=request.headers.get("X-NUCLIADB-USER", ""),
        processing_options=item.processing_options,
    )

    writer.kbid = kbid
    toprocess.kbid = kbid
    writer.uuid = uuid
    toprocess.uuid = uuid
    toprocess.source = Source.HTTP

    if item.slug:
        writer.slug = item.slug
        toprocess.slug = item.slug

    parse_audit(writer.audit, request)
    parse_basic(writer, item, toprocess)
    if item.origin is not None:
        parse_origin(writer.origin, item.origin)

    await parse_fields(
        writer=writer,
        item=item,
        toprocess=toprocess,
        kbid=kbid,
        uuid=uuid,
        x_skip_store=x_skip_store,
    )

    set_status(writer.basic, item)

    set_info_on_span({"nuclia.rid": uuid, "nuclia.kbid": kbid})

    try:
        seqid = await processing.send_to_process(toprocess, partition)
    except LimitsExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc))

    writer.source = BrokerMessage.MessageSource.WRITER
    await transaction.commit(writer, partition)

    return ResourceCreated(seqid=seqid, uuid=uuid)


@api.patch(
    f"/{KB_PREFIX}/{{kbid}}/{RESOURCE_PREFIX}/{{rid}}",
    status_code=200,
    name="Modify Resource",
    response_model=ResourceUpdated,
    tags=["Resources"],
)
@requires(NucliaDBRoles.WRITER)
@version(1)
async def modify_resource(
    request: Request,
    item: UpdateResourcePayload,
    kbid: str,
    rid: str,
    x_skip_store: bool = SKIP_STORE_DEFAULT,
):
    transaction = get_transaction()
    processing = get_processing()
    partitioning = get_partitioning()

    partition = partitioning.generate_partition(kbid, rid)

    writer = BrokerMessage()
    toprocess = PushPayload(
        uuid=rid,
        kbid=kbid,
        partition=partition,
        userid=request.headers.get("X-NUCLIADB-USER", ""),
        processing_options=item.processing_options,
    )

    writer.kbid = kbid
    writer.uuid = rid
    toprocess.kbid = kbid
    toprocess.uuid = rid
    toprocess.source = Source.HTTP

    parse_basic_modify(writer, item, toprocess)
    parse_audit(writer.audit, request)

    await parse_fields(
        writer=writer,
        item=item,
        toprocess=toprocess,
        kbid=kbid,
        uuid=rid,
        x_skip_store=x_skip_store,
    )

    set_status_modify(writer.basic, item)

    try:
        seqid = await processing.send_to_process(toprocess, partition)
    except LimitsExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc))

    writer.source = BrokerMessage.MessageSource.WRITER
    await transaction.commit(writer, partition)

    return ResourceUpdated(seqid=seqid)


@api.post(
    f"/{KB_PREFIX}/{{kbid}}/{RESOURCE_PREFIX}/{{rid}}/reprocess",
    status_code=202,
    name="Reprocess resource",
    response_model=ResourceUpdated,
    tags=["Resources"],
)
@requires(NucliaDBRoles.WRITER)
@version(1)
async def reprocess_resource(request: Request, kbid: str, rid: str):
    processing = get_processing()
    partitioning = get_partitioning()
    partition = partitioning.generate_partition(kbid, rid)

    toprocess = PushPayload(
        uuid=rid,
        kbid=kbid,
        partition=partition,
        userid=request.headers.get("X-NUCLIADB-USER", ""),
    )

    toprocess.kbid = kbid
    toprocess.uuid = rid
    toprocess.source = Source.HTTP

    storage = await get_storage(service_name=SERVICE_NAME)
    cache = await get_cache()
    driver = await get_driver()

    txn = await driver.begin()
    kb = KnowledgeBox(txn, storage, cache, kbid)

    resource = await kb.get(rid)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource does not exist")

    await extract_fields(resource=resource, toprocess=toprocess)

    if txn.open:
        await txn.abort()

    # Send current resource to reprocess.

    try:
        seqid = await processing.send_to_process(toprocess, partition)
    except LimitsExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc))

    return ResourceUpdated(seqid=seqid)


@api.delete(
    f"/{KB_PREFIX}/{{kbid}}/{RESOURCE_PREFIX}/{{rid}}",
    status_code=204,
    name="Delete Resource",
    tags=["Resources"],
)
@requires(NucliaDBRoles.WRITER)
@version(1)
async def delete_resource(request: Request, kbid: str, rid: str):

    set_info_on_span({"nuclia.kbid": kbid, "nucliadb.rid": rid})

    transaction = get_transaction()
    partitioning = get_partitioning()

    partition = partitioning.generate_partition(kbid, rid)
    writer = BrokerMessage()

    writer.kbid = kbid
    writer.uuid = rid
    writer.type = BrokerMessage.MessageType.DELETE

    parse_audit(writer.audit, request)

    # Create processing message
    await transaction.commit(writer, partition)

    return Response(status_code=204)


@api.post(
    f"/{KB_PREFIX}/{{kbid}}/{RESOURCE_PREFIX}/{{rid}}/reindex",
    status_code=204,
    name="Reindex Resource",
    tags=["Resources"],
)
@requires(NucliaDBRoles.WRITER)
@version(1)
async def reindex_resource(request: Request, kbid: str, rid: str):
    ingest = get_ingest()
    resource = IndexResource()
    resource.kbid = kbid
    resource.rid = rid
    await ingest.ReIndex(resource)  # type: ignore
    return Response(status_code=200)
