ALTER TABLE accounts ADD COLUMN nickname TEXT NOT NULL DEFAULT '';
ALTER TABLE accounts ADD COLUMN legacy_password_hash TEXT;
ALTER TABLE accounts ADD COLUMN gamespy_user_id INTEGER;
ALTER TABLE accounts ADD COLUMN gamespy_profile_id INTEGER;

ALTER TABLE campaigns ADD COLUMN next_mission_id INTEGER NOT NULL DEFAULT 1;

ALTER TABLE characters ADD COLUMN verification_id TEXT;
ALTER TABLE characters ADD COLUMN missions_played_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE news_stories ADD COLUMN timestamp INTEGER NOT NULL DEFAULT 0;
ALTER TABLE news_stories ADD COLUMN persistence INTEGER NOT NULL DEFAULT 3;
ALTER TABLE news_stories ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0;

-- Version 1 incorrectly required every auction catalog entry to already be an
-- instantiated Ship. Retail auctions identify catalog items before ownership,
-- so preserve that identity separately and make an awarded Ship optional.
ALTER TABLE auctions RENAME TO auctions_v1;

CREATE TABLE auctions (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    catalog_item_id INTEGER NOT NULL,
    ship_id INTEGER REFERENCES ships(id) ON DELETE SET NULL,
    bid_owner_character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    current_bid INTEGER NOT NULL,
    bid_maximum INTEGER NOT NULL DEFAULT 0,
    escrow INTEGER NOT NULL DEFAULT 0,
    turn_opened INTEGER NOT NULL DEFAULT 0,
    turn_bid_made INTEGER NOT NULL DEFAULT 0,
    turn_to_close INTEGER NOT NULL DEFAULT 0,
    closing INTEGER NOT NULL DEFAULT 0 CHECK (closing IN (0, 1)),
    UNIQUE (campaign_id, catalog_item_id)
);

INSERT INTO auctions(
    id, campaign_id, catalog_item_id, ship_id, bid_owner_character_id,
    current_bid, bid_maximum, escrow, turn_opened, turn_bid_made,
    turn_to_close, closing
)
SELECT
    id, campaign_id, ship_id, ship_id, bid_owner_character_id,
    current_bid, bid_maximum, escrow, turn_opened, turn_bid_made,
    turn_to_close, closing
FROM auctions_v1;

DROP TABLE auctions_v1;

CREATE INDEX auctions_bid_owner_idx ON auctions(bid_owner_character_id);

CREATE TABLE auction_settlements (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    catalog_item_id INTEGER NOT NULL,
    awarded_ship_id INTEGER REFERENCES ships(id) ON DELETE SET NULL,
    class_name TEXT NOT NULL,
    price INTEGER NOT NULL,
    turn INTEGER NOT NULL
);

CREATE TABLE import_history (
    id INTEGER PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_kind, source_sha256)
);

INSERT INTO schema_version(version) VALUES (2);
