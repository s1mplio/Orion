import functools
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.companion.memory.atomic_json import atomic_dump


def _locked(method):
    """
    Serialize access to the FAISS index and metadata.

    The companion API (FastAPI thread pool) and the
    vision loop can read and write memory concurrently.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class FAISSMemory:
    """
    Long-term semantic memory for Orion.

    FAISS stores embeddings.
    JSON stores metadata.

    Each memory tracks:
    - id
    - first_seen
    - last_confirmed
    - last_observed
    - observation
    """

    def __init__(
        self,
        max_memories: int = 100,
    ):
        self.max_memories = max_memories

        self._lock = threading.RLock()

        self.base_path = Path(__file__).resolve().parent

        self.index_path = (
            self.base_path / "orion_memory.faiss"
        )

        self.metadata_path = (
            self.base_path / "orion_memory.json"
        )

        print("Loading semantic memory model...")

        # Keep embeddings on CPU so they don't
        # compete with Orion's VLM/GPU workload.
        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            device="cpu",
        )

        self.dimension = (
            self.model.get_sentence_embedding_dimension()
        )

        self.index = faiss.IndexFlatIP(
            self.dimension
        )

        self.memories = []

        self._load()

    # =================================================
    # LOAD
    # =================================================

    def _load(self):
        """
        Load FAISS index + metadata.

        Older Orion memories that used only
        'timestamp' are migrated automatically.
        """

        # Metadata is the source of truth. The FAISS index
        # can always be rebuilt from it, so a missing or
        # unreadable index must not discard memories.
        if not self.metadata_path.exists():
            print(
                "Starting new FAISS memory index."
            )
            return

        try:
            with open(
                self.metadata_path,
                "r",
                encoding="utf-8",
            ) as file:
                memories = json.load(file)

            if not isinstance(memories, list):
                raise ValueError(
                    "Memory metadata must be a list."
                )

        except Exception as e:
            print(
                "Failed to load FAISS memory:",
                e,
            )

            # Keep the unreadable file so the next save
            # does not silently overwrite the user's
            # memories.
            backup_path = self.metadata_path.with_suffix(
                ".json.corrupt-"
                + datetime.now().strftime("%Y%m%d%H%M%S")
            )

            try:
                os.replace(
                    self.metadata_path,
                    backup_path,
                )
                print(
                    "Unreadable memory file moved to:",
                    backup_path,
                )
            except OSError as backup_error:
                print(
                    "Could not back up memory file:",
                    backup_error,
                )

            print(
                "Starting a fresh in-memory "
                "FAISS index."
            )

            self.index = faiss.IndexFlatIP(
                self.dimension
            )

            self.memories = []
            return

        self.memories = memories

        changed = False

        try:
            self.index = faiss.read_index(
                str(self.index_path)
            )
        except Exception as e:
            print(
                "FAISS index unavailable, "
                "rebuilding from metadata:",
                e,
            )

            self.index = faiss.IndexFlatIP(
                self.dimension
            )

        if self.index.d != self.dimension:
            print(
                "FAISS index dimension does not match "
                "the embedding model."
            )

            self.index = faiss.IndexFlatIP(
                self.dimension
            )

        try:

            # -----------------------------------------
            # Migrate older metadata format
            # -----------------------------------------

            for position, memory in enumerate(
                self.memories,
                start=1,
            ):
                if "id" not in memory:
                    memory["id"] = position
                    changed = True

                old_timestamp = memory.get(
                    "timestamp"
                )

                if "first_seen" not in memory:
                    memory["first_seen"] = (
                        old_timestamp
                        or datetime.now().isoformat()
                    )
                    changed = True

                if "last_confirmed" not in memory:
                    memory["last_confirmed"] = (
                        old_timestamp
                        or memory["first_seen"]
                    )
                    changed = True

                if "last_observed" not in memory:
                    memory["last_observed"] = (
                        old_timestamp
                        or memory["last_confirmed"]
                    )
                    changed = True

            # -----------------------------------------
            # Ensure FAISS IDs align with metadata
            # -----------------------------------------

            if (
                self.index.ntotal
                != len(self.memories)
            ):
                print(
                    "FAISS index and metadata "
                    "are out of sync."
                )

                print(
                    "Rebuilding FAISS index..."
                )

                self._rebuild_index()

                changed = True

            if changed:
                self._save()

            print(
                f"FAISS memory loaded: "
                f"{len(self.memories)} memories"
            )

        except Exception as e:
            # Metadata loaded but migration/rebuild failed.
            # Keep the memories in RAM and do not overwrite
            # the files on disk.
            print(
                "Failed to prepare FAISS memory:",
                e,
            )

    # =================================================
    # SAVE
    # =================================================

    def _save(self):
        """
        Persist FAISS vectors and metadata.

        Both files are written atomically so a crash
        mid-write cannot leave a truncated memory file.
        """

        temporary_index = self.index_path.with_suffix(
            self.index_path.suffix + ".tmp"
        )

        faiss.write_index(
            self.index,
            str(temporary_index),
        )

        os.replace(
            temporary_index,
            self.index_path,
        )

        atomic_dump(
            self.metadata_path,
            self.memories,
        )

    # =================================================
    # EMBEDDING
    # =================================================

    def _embed(
        self,
        text: str,
    ) -> np.ndarray:
        """
        Create normalized 384-dimensional embedding.
        """

        vector = self.model.encode(
            [text],
            normalize_embeddings=True,
        )

        return np.asarray(
            vector,
            dtype=np.float32,
        )

    # =================================================
    # NEXT MEMORY ID
    # =================================================

    def _next_memory_id(self) -> int:
        if not self.memories:
            return 1

        return (
            max(
                memory.get("id", 0)
                for memory in self.memories
            )
            + 1
        )

    # =================================================
    # ADD NEW SEMANTIC MEMORY
    # =================================================

    @_locked
    def add(
        self,
        observation: str,
    ):
        """
        Add a genuinely new semantic memory.

        Duplicate detection happens in MemoryManager.
        """

        if not observation:
            return None

        observation = observation.strip()

        if not observation:
            return None

        now = datetime.now().isoformat()

        memory_id = self._next_memory_id()

        print(
            "Creating semantic embedding..."
        )

        vector = self._embed(
            observation
        )

        self.index.add(
            vector
        )

        memory = {
            "id": memory_id,
            "first_seen": now,
            "last_confirmed": now,
            "last_observed": now,
            "observation": observation,
        }

        self.memories.append(
            memory
        )

        # ---------------------------------------------
        # Keep memory bounded
        # ---------------------------------------------

        if (
            len(self.memories)
            > self.max_memories
        ):
            self.memories = self.memories[
                -self.max_memories:
            ]

            self._rebuild_index()

        self._save()

        print(
            f"FAISS memory stored "
            f"(ID {memory_id})"
        )

        print(
            observation
        )

        return memory

    # =================================================
    # UPDATE TEMPORAL STATE
    # =================================================

    @_locked
    def update_temporal_state(
        self,
        memory_id: int,
        last_confirmed: Optional[str] = None,
        last_observed: Optional[str] = None,
    ) -> bool:
        """
        Update only temporal metadata.

        No new embedding is generated because
        the semantic observation hasn't changed.
        """

        for memory in self.memories:
            if (
                memory.get("id")
                != memory_id
            ):
                continue

            if last_confirmed is not None:
                memory["last_confirmed"] = (
                    last_confirmed
                )

            if last_observed is not None:
                memory["last_observed"] = (
                    last_observed
                )

            self._save()

            print(
                f"TEMPORAL_MEMORY_UPDATED: "
                f"{memory_id}"
            )

            return True

        print(
            f"Memory ID {memory_id} "
            f"not found."
        )

        return False

    # =================================================
    # GET MEMORY BY ID
    # =================================================

    @_locked
    def get_by_id(
        self,
        memory_id: int,
    ):
        for memory in self.memories:
            if (
                memory.get("id")
                == memory_id
            ):
                return dict(memory)

        return None

    # =================================================
    # REBUILD FAISS INDEX
    # =================================================

    def _rebuild_index(self):
        """
        Recreate the FAISS index from metadata.

        Needed when memories are trimmed or
        index/metadata become out of sync.
        """

        self.index = faiss.IndexFlatIP(
            self.dimension
        )

        if not self.memories:
            return

        texts = [
            memory["observation"]
            for memory in self.memories
        ]

        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
        )

        vectors = np.asarray(
            vectors,
            dtype=np.float32,
        )

        self.index.add(
            vectors
        )

    # =================================================
    # SEMANTIC SEARCH
    # =================================================

    @_locked
    def search(
        self,
        query: str,
        limit: int = 5,
    ):
        """
        Retrieve memories semantically related
        to the query.
        """

        if not query:
            return []

        if not self.memories:
            return []

        query_vector = self._embed(
            query
        )

        k = min(
            limit,
            len(self.memories),
        )

        scores, indices = (
            self.index.search(
                query_vector,
                k,
            )
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):
            if index < 0:
                continue

            if (
                index
                >= len(self.memories)
            ):
                continue

            memory = dict(
                self.memories[index]
            )

            memory["similarity"] = float(
                score
            )

            results.append(
                memory
            )

        return results

    # =================================================
    # RECENT MEMORIES
    # =================================================

    @_locked
    def recent(
        self,
        limit: int = 5,
    ):
        """
        Return most recently observed memories.
        """

        memories = sorted(
            self.memories,
            key=lambda memory: (
                memory.get("last_observed")
                or memory.get("last_confirmed")
                or memory.get("first_seen")
                or memory.get(
                    "timestamp",
                    "",
                )
            ),
            reverse=True,
        )

        return [
            dict(memory)
            for memory in memories[:limit]
        ]

    # =================================================
    # TIME-AWARE RECALL
    # =================================================

    @_locked
    def recent_minutes(
        self,
        minutes: int = 10,
    ):
        """
        Return memories that Orion has observed
        within the requested time window.

        Uses last_observed first, then falls back
        to last_confirmed/first_seen/old timestamp.
        """

        if minutes <= 0:
            return []

        now = datetime.now()

        results = []

        for memory in self.memories:
            timestamp_text = (
                memory.get("last_observed")
                or memory.get("last_confirmed")
                or memory.get("first_seen")
                or memory.get("timestamp")
            )

            if not timestamp_text:
                continue

            try:
                timestamp = (
                    datetime.fromisoformat(
                        timestamp_text
                    )
                )

            except (
                ValueError,
                TypeError,
            ):
                continue

            age_seconds = (
                now - timestamp
            ).total_seconds()

            if age_seconds < 0:
                continue

            if (
                age_seconds
                <= minutes * 60
            ):
                results.append(
                    dict(memory)
                )

        results.sort(
            key=lambda memory: (
                memory.get("last_observed")
                or memory.get("last_confirmed")
                or memory.get("first_seen")
                or memory.get(
                    "timestamp",
                    "",
                )
            ),
            reverse=True,
        )

        return results