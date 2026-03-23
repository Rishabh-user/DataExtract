"""Elasticsearch client and index management (optional)."""

from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "document_id": {"type": "integer"},
            "file_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "file_type": {"type": "keyword"},
            "source": {"type": "keyword"},
            "page_number": {"type": "integer"},
            "content": {"type": "text", "analyzer": "standard"},
            "metadata": {"type": "object", "enabled": True},
            "upload_date": {"type": "date"},
            "created_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}


class ElasticsearchClient:
    """Wrapper around the async Elasticsearch client. Fully optional."""

    def __init__(self) -> None:
        self._client = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def connect(self) -> None:
        if not settings.ELASTICSEARCH_ENABLED:
            logger.info("Elasticsearch disabled via ELASTICSEARCH_ENABLED=false.")
            return

        try:
            from elasticsearch import AsyncElasticsearch

            kwargs: dict[str, Any] = {"hosts": [settings.ELASTICSEARCH_URL]}
            if settings.ELASTICSEARCH_USER and settings.ELASTICSEARCH_PASSWORD:
                kwargs["basic_auth"] = (
                    settings.ELASTICSEARCH_USER,
                    settings.ELASTICSEARCH_PASSWORD,
                )
            self._client = AsyncElasticsearch(**kwargs)
            await self._ensure_index()
            self._available = True
            logger.info("Elasticsearch connected at %s", settings.ELASTICSEARCH_URL)
        except Exception as e:
            self._available = False
            logger.warning("Elasticsearch unavailable: %s — search will use DB fallback.", e)

    async def _ensure_index(self) -> None:
        if not self._client:
            return
        if not await self._client.indices.exists(index=settings.ELASTICSEARCH_INDEX):
            await self._client.indices.create(
                index=settings.ELASTICSEARCH_INDEX, body=INDEX_MAPPING
            )
            logger.info("Created Elasticsearch index: %s", settings.ELASTICSEARCH_INDEX)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            logger.info("Elasticsearch connection closed.")

    async def index_document(self, doc_id: str, body: dict[str, Any]) -> None:
        if not self._available or not self._client:
            return
        try:
            await self._client.index(
                index=settings.ELASTICSEARCH_INDEX, id=doc_id, document=body
            )
        except Exception as e:
            logger.warning("ES index failed for %s: %s", doc_id, e)

    async def search(
        self,
        query: str,
        file_type: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        if not self._available or not self._client:
            return {"hits": {"total": {"value": 0}, "hits": []}}

        must_clauses: list[dict] = [
            {"multi_match": {"query": query, "fields": ["content", "file_name"]}}
        ]
        filter_clauses: list[dict] = []

        if file_type:
            filter_clauses.append({"term": {"file_type": file_type}})
        if source:
            filter_clauses.append({"term": {"source": source}})

        body = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "from": (page - 1) * size,
            "size": size,
            "highlight": {
                "fields": {"content": {"fragment_size": 200, "number_of_fragments": 3}}
            },
        }

        result = await self._client.search(index=settings.ELASTICSEARCH_INDEX, body=body)
        return result.body

    async def delete_document(self, doc_id: str) -> None:
        if not self._available or not self._client:
            return
        await self._client.delete(
            index=settings.ELASTICSEARCH_INDEX, id=doc_id, ignore=[404]
        )


# Singleton instance
es_client = ElasticsearchClient()


async def get_es_client() -> ElasticsearchClient:
    return es_client
