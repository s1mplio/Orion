import sqlite3
from datetime import datetime
from pathlib import Path


class MemoryStore:

    def __init__(self, max_memories: int = 100):

        self.max_memories = max_memories

        self.db_path = (
            Path(__file__).resolve().parents[3]
            / "orion_memory.db"
        )

        print(
            "MemoryStore database:",
            self.db_path
        )

        self._initialize_database()

    # =================================================
    # DATABASE INITIALIZATION
    # =================================================

    def _initialize_database(self):

        with sqlite3.connect(
            self.db_path
        ) as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    observation TEXT NOT NULL
                )
                """
            )

            connection.commit()

        print(
            "MemoryStore database initialized."
        )

    # =================================================
    # ADD MEMORY
    # =================================================

    def add(self, observation: str):

        if not observation:
            return

        observation = observation.strip()

        if not observation:
            return

        timestamp = datetime.now().isoformat()

        print(
            "WRITING MEMORY:",
            observation
        )

        print(
            "MEMORY DB PATH:",
            self.db_path
        )

        with sqlite3.connect(
            self.db_path
        ) as connection:

            connection.execute(
                """
                INSERT INTO memories (
                    timestamp,
                    observation
                )
                VALUES (?, ?)
                """,
                (
                    timestamp,
                    observation,
                ),
            )

            connection.commit()

            # Keep only newest memories.
            connection.execute(
                """
                DELETE FROM memories
                WHERE id NOT IN (
                    SELECT id
                    FROM memories
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (
                    self.max_memories,
                ),
            )

            connection.commit()

            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM memories
                """
            ).fetchone()[0]

        print(
            "MEMORY WRITE SUCCESS."
        )

        print(
            "TOTAL MEMORIES:",
            count
        )

    # =================================================
    # RECENT MEMORIES
    # =================================================

    def get_recent(
        self,
        limit: int = 10
    ):

        with sqlite3.connect(
            self.db_path
        ) as connection:

            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    timestamp,
                    observation
                FROM memories
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()

        return [
            {
                "timestamp": row["timestamp"],
                "observation": row["observation"],
            }
            for row in reversed(rows)
        ]

    # =================================================
    # SEARCH MEMORIES
    # =================================================

    def search(
        self,
        query: str
    ):

        # No query → recent context
        if not query:

            print(
                "No query provided. "
                "Using recent memories."
            )

            return self.get_recent(5)

        query_words = [
            word.strip(
                ".,!?;:'\"()[]{}"
            )
            for word in query.lower().split()
        ]

        query_words = [
            word
            for word in query_words
            if len(word) > 2
        ]

        # Query contains no useful words.
        if not query_words:

            print(
                "No useful query words. "
                "Using recent memories."
            )

            return self.get_recent(5)

        with sqlite3.connect(
            self.db_path
        ) as connection:

            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    timestamp,
                    observation
                FROM memories
                ORDER BY id DESC
                """
            ).fetchall()

        results = []

        for row in rows:

            text = row[
                "observation"
            ].lower()

            score = sum(
                1
                for word in query_words
                if word in text
            )

            if score > 0:

                results.append(
                    (
                        score,
                        {
                            "timestamp":
                                row["timestamp"],

                            "observation":
                                row["observation"],
                        },
                    )
                )

        # ---------------------------------------------
        # Keyword matches found
        # ---------------------------------------------

        if results:

            results.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            memories = [
                memory
                for _, memory in results[:10]
            ]

            print(
                "Memory search results:",
                len(memories)
            )

            return memories

        # ---------------------------------------------
        # No keyword match
        #
        # Use recent visual context.
        # ---------------------------------------------

        print(
            "No keyword memory match."
        )

        print(
            "Using recent visual memories."
        )

        return self.get_recent(5)