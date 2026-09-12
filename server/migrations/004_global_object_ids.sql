-- Retail uses one database-wide allocator for persistent object identities.
-- Keep allocation state separate from SQLite rowid sequences so characters,
-- ships, officers, auctions, news, and missions cannot reuse one another's IDs.
CREATE TABLE object_id_sequence (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    next_id INTEGER NOT NULL CHECK (next_id > 0)
);

CREATE TABLE shipyard_catalog (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    race INTEGER NOT NULL,
    catalog_index INTEGER NOT NULL,
    auction_id INTEGER NOT NULL UNIQUE,
    item_id INTEGER NOT NULL UNIQUE,
    PRIMARY KEY (campaign_id, race, catalog_index)
);

CREATE TABLE officer_review_catalog (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    race INTEGER NOT NULL,
    candidate_index INTEGER NOT NULL,
    officer_id INTEGER NOT NULL UNIQUE,
    PRIMARY KEY (campaign_id, race, candidate_index)
);

INSERT INTO object_id_sequence(singleton, next_id)
SELECT 1, MAX(max_id) + 1
FROM (
    SELECT 17 AS max_id
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM characters
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM ships
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM officers
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM auctions
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM news_stories
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM prepared_missions
    UNION ALL SELECT COALESCE(MAX(id), 0) FROM auction_settlements
);

INSERT INTO schema_version(version) VALUES (4);
