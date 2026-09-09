PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    map_id TEXT NOT NULL,
    epoch_unix REAL NOT NULL CHECK (epoch_unix >= 0),
    initial_turn INTEGER NOT NULL CHECK (initial_turn >= 0),
    next_news_id INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    account_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT,
    verification_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    character_name TEXT NOT NULL,
    client_address TEXT NOT NULL DEFAULT '',
    race INTEGER NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0,
    rating INTEGER NOT NULL DEFAULT 1500,
    prestige INTEGER NOT NULL DEFAULT 0,
    lifetime_prestige INTEGER NOT NULL DEFAULT 0,
    disrepute INTEGER NOT NULL DEFAULT 0,
    lifetime_disrepute INTEGER NOT NULL DEFAULT 0,
    position_x INTEGER NOT NULL,
    position_y INTEGER NOT NULL,
    homeworld_x INTEGER NOT NULL,
    homeworld_y INTEGER NOT NULL,
    destination_x INTEGER NOT NULL DEFAULT -1,
    destination_y INTEGER NOT NULL DEFAULT -1,
    flags INTEGER NOT NULL DEFAULT 0,
    UNIQUE (campaign_id, account_id),
    UNIQUE (campaign_id, character_name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS ships (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    owner_character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    race INTEGER NOT NULL,
    class_type INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    loadout_name TEXT NOT NULL,
    name TEXT NOT NULL,
    epv INTEGER NOT NULL,
    damage REAL NOT NULL DEFAULT 1.0 CHECK (damage >= 0.0 AND damage <= 1.0),
    flags INTEGER NOT NULL DEFAULT 0,
    turn_created INTEGER NOT NULL DEFAULT 0,
    in_auction INTEGER NOT NULL DEFAULT 0 CHECK (in_auction IN (0, 1))
);

CREATE INDEX IF NOT EXISTS ships_owner_idx ON ships(owner_character_id);

CREATE TABLE IF NOT EXISTS ship_stores (
    ship_id INTEGER PRIMARY KEY REFERENCES ships(id) ON DELETE CASCADE,
    shuttles INTEGER NOT NULL CHECK (shuttles >= 0),
    marines INTEGER NOT NULL CHECK (marines >= 0),
    mines INTEGER NOT NULL CHECK (mines >= 0)
);

CREATE TABLE IF NOT EXISTS ship_loadout_items (
    ship_id INTEGER NOT NULL REFERENCES ships(id) ON DELETE CASCADE,
    slot_index INTEGER NOT NULL CHECK (slot_index >= 0),
    item TEXT NOT NULL,
    PRIMARY KEY (ship_id, slot_index)
);

CREATE TABLE IF NOT EXISTS officers (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ship_id INTEGER REFERENCES ships(id) ON DELETE SET NULL,
    station INTEGER,
    name TEXT NOT NULL,
    race INTEGER NOT NULL,
    worth INTEGER NOT NULL DEFAULT 0,
    profile_json TEXT NOT NULL DEFAULT '{}',
    at_base_id INTEGER,
    in_review_character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    UNIQUE (ship_id, station)
);

CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ship_id INTEGER NOT NULL REFERENCES ships(id) ON DELETE CASCADE,
    bid_owner_character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    current_bid INTEGER NOT NULL,
    bid_maximum INTEGER NOT NULL DEFAULT 0,
    escrow INTEGER NOT NULL DEFAULT 0,
    turn_opened INTEGER NOT NULL,
    turn_bid_made INTEGER NOT NULL DEFAULT 0,
    turn_to_close INTEGER NOT NULL,
    closing INTEGER NOT NULL DEFAULT 0 CHECK (closing IN (0, 1))
);

CREATE TABLE IF NOT EXISTS news_stories (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn INTEGER NOT NULL,
    channel TEXT NOT NULL,
    priority TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prepared_missions (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    mission_json TEXT NOT NULL,
    UNIQUE (campaign_id, character_id, id)
);

CREATE TABLE IF NOT EXISTS banned_identities (
    id INTEGER PRIMARY KEY,
    ip_address TEXT,
    account_name TEXT COLLATE NOCASE,
    reason TEXT NOT NULL DEFAULT ''
);

INSERT OR IGNORE INTO schema_version(version) VALUES (1);
