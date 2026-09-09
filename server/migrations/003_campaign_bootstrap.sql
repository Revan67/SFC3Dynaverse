ALTER TABLE campaigns ADD COLUMN turns_per_year INTEGER NOT NULL DEFAULT 10000;
ALTER TABLE campaigns ADD COLUMN milliseconds_per_turn INTEGER NOT NULL DEFAULT 120000;
ALTER TABLE campaigns ADD COLUMN base_year INTEGER NOT NULL DEFAULT 56200;
ALTER TABLE campaigns ADD COLUMN asset_manifest_sha256 TEXT;

CREATE TABLE asset_manifest (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    source_tier TEXT NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    sha256 TEXT NOT NULL,
    PRIMARY KEY (campaign_id, relative_path)
);

CREATE TABLE map_hexes (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    client_record BLOB NOT NULL,
    PRIMARY KEY (campaign_id, x, y)
);

CREATE TABLE political_tensions (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    race_a INTEGER NOT NULL,
    race_b INTEGER NOT NULL,
    tension INTEGER NOT NULL,
    PRIMARY KEY (campaign_id, race_a, race_b)
);

INSERT INTO schema_version(version) VALUES (3);
