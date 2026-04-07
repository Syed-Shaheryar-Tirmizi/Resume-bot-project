from __future__ import annotations

import logging
import threading
import uuid as py_uuid
from dataclasses import dataclass

import weaviate
import weaviate.classes as wvc
import weaviate.util as wutil
from weaviate.auth import AuthApiKey
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import MetadataQuery

from backend.config import settings
from backend.errors import ServiceError, weaviate_unavailable

logger = logging.getLogger(__name__)

COLLECTION = "ResumeInsightResume"

_client: weaviate.WeaviateClient | None = None
_lock = threading.Lock()


@dataclass
class MatchResult:
    resume_id: str
    content: str
    title: str
    score: float


def _connect() -> weaviate.WeaviateClient:
    if settings.weaviate_cloud_mode():
        if not settings.weaviate_api_key:
            raise weaviate_unavailable(
                "WEAVIATE_API_KEY is required when WEAVIATE_URL is set (Weaviate Cloud)."
            )
        cluster_url = settings.weaviate_cluster_url()
        logger.info("Connecting to Weaviate Cloud at %s", cluster_url)
        extra = wvc.init.AdditionalConfig(
            timeout=wvc.init.Timeout(
                init=settings.weaviate_timeout_init,
                query=60.0,
                insert=120.0,
            )
        )
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=cluster_url,
            auth_credentials=AuthApiKey(settings.weaviate_api_key),
            additional_config=extra,
            skip_init_checks=settings.weaviate_skip_init_checks,
        )
    logger.info(
        "Connecting to local Weaviate at %s:%s",
        settings.weaviate_http_host,
        settings.weaviate_http_port,
    )
    return weaviate.connect_to_local(
        host=settings.weaviate_http_host,
        port=settings.weaviate_http_port,
        grpc_port=settings.weaviate_grpc_port,
        additional_config=wvc.init.AdditionalConfig(
            timeout=wvc.init.Timeout(init=settings.weaviate_timeout_init, query=60.0, insert=120.0)
        ),
    )


def _ensure_collection(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists(COLLECTION):
        return
    logger.info("Creating Weaviate collection %s", COLLECTION)
    client.collections.create(
        name=COLLECTION,
        properties=[
            Property(name="resume_id", data_type=DataType.TEXT),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="content", data_type=DataType.TEXT),
        ],
        vectorizer_config=Configure.Vectorizer.none(),
    )


def init_weaviate() -> None:
    """Connect and ensure schema. Required at startup; raises ServiceError on failure."""
    global _client
    with _lock:
        if _client is not None:
            return
        tmp: weaviate.WeaviateClient | None = None
        try:
            tmp = _connect()
            _ensure_collection(tmp)
            if not tmp.is_ready():
                raise RuntimeError("Weaviate cluster is not ready")
            _client = tmp
            tmp = None
        except ServiceError:
            raise
        except Exception as e:
            logger.exception("Weaviate initialization failed")
            raise weaviate_unavailable(
                "Cannot connect to Weaviate. Install and start a local instance "
                "(see https://weaviate.io/developers/weaviate/installation) or set "
                "WEAVIATE_URL and WEAVIATE_API_KEY for Weaviate Cloud. "
                f"Details: {e}"
            ) from e
        finally:
            if tmp is not None:
                try:
                    tmp.close()
                except Exception:
                    pass


def shutdown_weaviate() -> None:
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                logger.warning("Weaviate close failed", exc_info=True)
            _client = None


def is_connected() -> bool:
    if _client is None:
        return False
    try:
        return _client.is_ready()
    except Exception:
        return False


def _require_client() -> weaviate.WeaviateClient:
    if _client is None:
        raise weaviate_unavailable(
            "Vector database is not initialized. Restart the API server after fixing configuration."
        )
    return _client


def _resume_uuid(resume_id: str) -> py_uuid.UUID:
    return py_uuid.UUID(wutil.generate_uuid5(resume_id, COLLECTION))


def index_resume(resume_id: str, title: str, content: str) -> str:
    from backend.services.embeddings import embed_texts

    client = _require_client()
    vectors = embed_texts([content])
    vector = vectors[0]
    coll = client.collections.get(COLLECTION)
    uid = _resume_uuid(resume_id)
    try:
        coll.data.delete_by_id(uid)
    except Exception:
        pass
    try:
        coll.data.insert(
            uuid=uid,
            properties={"resume_id": resume_id, "title": title, "content": content},
            vector=vector,
        )
    except Exception as e:
        logger.exception("Weaviate insert failed")
        raise weaviate_unavailable(f"Failed to index resume in Weaviate: {e}") from e
    return resume_id


def remove_resume(resume_id: str) -> None:
    client = _require_client()
    coll = client.collections.get(COLLECTION)
    try:
        coll.data.delete_by_id(_resume_uuid(resume_id))
    except Exception:
        pass


def match_job(job_text: str, top_k: int = 5) -> list[MatchResult]:
    from backend.services.embeddings import embed_texts

    client = _require_client()
    vectors = embed_texts([job_text])
    qv = vectors[0]
    coll = client.collections.get(COLLECTION)
    try:
        res = coll.query.near_vector(
            near_vector=qv,
            limit=top_k,
            return_metadata=MetadataQuery(distance=True),
        )
    except Exception as e:
        logger.exception("Weaviate query failed")
        raise weaviate_unavailable(f"Semantic search failed: {e}") from e
    out: list[MatchResult] = []
    for o in res.objects:
        props = o.properties or {}
        dist = o.metadata.distance if o.metadata else None
        score = 1.0 - float(dist) if dist is not None else 0.0
        out.append(
            MatchResult(
                resume_id=str(props.get("resume_id", "")),
                title=str(props.get("title", "")),
                content=str(props.get("content", "")),
                score=score,
            )
        )
        return out
