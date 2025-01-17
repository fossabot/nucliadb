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
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

FIELD_TYPE_CHAR_MAP = {
    "c": "conversation",
    "d": "datetime",
    "f": "file",
    "k": "keywordset",
    "l": "layout",
    "u": "link",
    "t": "text",
    # "a": "generic",
}

STORAGE_FILE_MATCH = re.compile(
    r"/?kbs/(?P<kbid>[^/]+)/r/(?P<rid>[^/]+)/(?P<download_type>[fe])/(?P<field_type>\w)/(?P<field_id>[^/]+)/?(?P<key>.*)?"
)
DOWNLOAD_TYPE_MAP = {"f": "field", "e": "extracted"}
DOWNLOAD_URI = (
    "/kb/{kbid}/resource/{rid}/{field_type}/{field_id}/download/{download_type}/{key}"
)


class FieldID(BaseModel):
    class FieldType(Enum):
        FILE = "file"
        LINK = "link"
        DATETIME = "datetime"
        KEYWORDSET = "keywordset"
        TEXT = "text"
        LAYOUT = "layout"
        GENERIC = "generic"
        CONVERSATION = "conversation"

    field_type: FieldType
    field: str


class FileB64(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    payload: str
    md5: str


class CloudFile(BaseModel):
    uri: Optional[str]
    size: Optional[int]
    content_type: Optional[str]
    bucket_name: Optional[str]

    class Source(Enum):
        FLAPS = "FLAPS"
        GCS = "GCS"
        S3 = "S3"
        LOCAL = "LOCAL"

    source: Optional[Source]
    filename: Optional[str]
    resumable_uri: Optional[str]
    offset: Optional[int]
    upload_uri: Optional[str]
    parts: Optional[List[str]]
    old_uri: Optional[str]
    old_bucket: Optional[str]
    md5: Optional[str]


class CloudLink(BaseModel):
    uri: Optional[str]
    size: Optional[int]
    content_type: Optional[str]
    filename: Optional[str]

    @staticmethod
    def format_reader_download_uri(uri: str) -> str:
        match = STORAGE_FILE_MATCH.match(uri)
        if not match:
            return uri

        url_params = match.groupdict()
        url_params["download_type"] = DOWNLOAD_TYPE_MAP[url_params["download_type"]]
        url_params["field_type"] = FIELD_TYPE_CHAR_MAP[url_params["field_type"]]
        return DOWNLOAD_URI.format(**url_params).rstrip("/")

    def dict(self, **kwargs):
        self.uri = self.format_reader_download_uri(self.uri)
        return BaseModel.dict(self)


class FieldTypeName(str, Enum):
    """
    This map assumes that both values and extracted data field containers
    use the same names for its fields. See models.ResourceFieldValues and
    models.ResourceFieldExtractedData
    """

    TEXT = "text"
    FILE = "file"
    LINK = "link"
    LAYOUT = "layout"
    CONVERSATION = "conversation"
    KEYWORDSET = "keywordset"
    DATETIME = "datetime"
    GENERIC = "generic"


class Classification(BaseModel):
    labelset: str
    label: str


class Sentence(BaseModel):
    start: Optional[int]
    end: Optional[int]
    key: Optional[str]


class Paragraph(BaseModel):
    start: Optional[int]
    end: Optional[int]
    start_seconds: Optional[List[int]]
    end_seconds: Optional[List[int]]

    class TypeParagraph(str, Enum):
        TEXT = "TEXT"
        OCR = "OCR"
        INCEPTION = "INCEPTION"
        DESCRIPTION = "DESCRIPTION"
        TRANSCRIPT = "TRANSCRIPT"
        TITLE = "TITLE"

    kind: Optional[TypeParagraph]
    classifications: Optional[List[Classification]]
    sentences: Optional[List[Sentence]]
    key: Optional[str]


class Shards(BaseModel):
    shards: Optional[List[str]]
