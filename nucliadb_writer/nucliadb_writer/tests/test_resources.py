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
from datetime import datetime
from typing import Callable

import pytest
from asynctest.mock import CoroutineMock  # type: ignore
from httpx import AsyncClient

import nucliadb_models
from nucliadb_ingest.orm.resource import Resource
from nucliadb_ingest.processing import PushPayload
from nucliadb_models.resource import NucliaDBRoles
from nucliadb_writer.api.v1.router import KB_PREFIX, RESOURCE_PREFIX, RESOURCES_PREFIX
from nucliadb_writer.tests.test_fields import (
    TEST_CONVERSATION_PAYLOAD,
    TEST_DATETIMES_PAYLOAD,
    TEST_FILE_PAYLOAD,
    TEST_KEYWORDSETS_PAYLOAD,
    TEST_LAYOUT_PAYLOAD,
    TEST_LINK_PAYLOAD,
    TEST_TEXT_PAYLOAD,
)


@pytest.mark.asyncio
async def test_resource_crud(writer_api, knowledgebox_writer):
    knowledgebox_id = knowledgebox_writer
    async with writer_api(roles=[NucliaDBRoles.WRITER]) as client:
        # Test create resource
        resp = await client.post(
            f"/{KB_PREFIX}/{knowledgebox_id}/{RESOURCES_PREFIX}",
            json={
                "slug": "resource1",
                "title": "My resource",
                "summary": "Some summary",
                "icon": "image/png",
                "layout": "layout",
                "metadata": {
                    "language": "en",
                    "metadata": {"key1": "value1", "key2": "value2"},
                },
                "fieldmetadata": [
                    {
                        "paragraphs": [
                            {
                                "key": "paragraph1",
                                "classifications": [
                                    {"labelset": "ls1", "label": "label1"}
                                ],
                            }
                        ],
                        "token": [{"token": "token1", "klass": "klass1"}],
                        "field": {"field": "text1", "field_type": "text"},
                    }
                ],
                "usermetadata": {
                    "classifications": [{"labelset": "ls1", "label": "label1"}],
                    "relations": [
                        {
                            "relation": "CHILD",
                            "properties": {
                                "prop1": "value",
                            },
                            "resource": "resource_uuid",
                        }
                    ],
                },
                "origin": {
                    "source_id": "source_id",
                    "url": "http://some_source",
                    "created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "modified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "metadata": {"key1": "value1", "key2": "value2"},
                    "tags": ["tag1", "tag2"],
                    "colaborators": ["col1", "col2"],
                    "filename": "file.pdf",
                    "related": ["related1"],
                },
                "texts": {"text1": TEST_TEXT_PAYLOAD},
                "links": {"link1": TEST_LINK_PAYLOAD},
                "files": {"file1": TEST_FILE_PAYLOAD},
                "layouts": {"layout1": TEST_LAYOUT_PAYLOAD},
                "conversations": {"conv1": TEST_CONVERSATION_PAYLOAD},
                "keywordsets": {"keywordset1": TEST_KEYWORDSETS_PAYLOAD},
                "datetimes": {"datetime1": TEST_DATETIMES_PAYLOAD},
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert "uuid" in data
        assert "seqid" in data
        rid = data["uuid"]

        # Test update resource
        resp = await client.patch(
            f"/{KB_PREFIX}/{knowledgebox_id}/{RESOURCE_PREFIX}/{rid}",
            json={},
        )
        assert resp.status_code == 200

        data = resp.json()

        assert "seqid" in data

        # Test delete resource
        resp = await client.delete(
            f"/{KB_PREFIX}/{knowledgebox_id}/{RESOURCE_PREFIX}/{rid}",
        )
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_reprocess_resource(
    writer_api: Callable[..., AsyncClient], test_resource: Resource, mocker
) -> None:
    rsc = test_resource
    kbid = rsc.kb.kbid
    rid = rsc.uuid

    from nucliadb_writer.utilities import get_processing

    processing = get_processing()

    original = processing.send_to_process
    mocker.patch.object(
        processing, "send_to_process", CoroutineMock(side_effect=original)
    )

    async with writer_api(roles=[NucliaDBRoles.WRITER]) as client:
        resp = await client.post(
            f"/{KB_PREFIX}/{kbid}/resource/{rid}/reprocess",
        )
        assert resp.status_code == 202

        assert processing.send_to_process.call_count == 1  # type: ignore
        payload = processing.send_to_process.call_args[0][0]  # type: ignore
        assert isinstance(payload, PushPayload)
        assert payload.uuid == rid
        assert payload.kbid == kbid

        assert isinstance(payload.filefield.get("file1"), str)
        assert payload.filefield["file1"] == "DUMMYJWT"
        assert isinstance(payload.linkfield.get("link1"), nucliadb_models.LinkUpload)
        assert isinstance(payload.textfield.get("text1"), nucliadb_models.Text)
        assert isinstance(
            payload.layoutfield.get("layout1"), nucliadb_models.LayoutDiff
        )
        assert payload.layoutfield["layout1"].blocks["field1"].file == "DUMMYJWT"
        assert isinstance(
            payload.conversationfield.get("conv1"), nucliadb_models.PushConversation
        )
        assert (
            payload.conversationfield["conv1"].messages[33].content.attachments[0]
            == "DUMMYJWT"
        )
        assert (
            payload.conversationfield["conv1"].messages[33].content.attachments[1]
            == "DUMMYJWT"
        )
