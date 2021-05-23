DROP TABLE IF EXISTS metadata_doggies;
CREATE TABLE metadata_doggies(
        id SERIAL,
        doggie_id INT UNIQUE,
        doggie_metadata JSON NOT NULL,
        doggie_image VARCHAR NOT NULL,
        is_visible BOOLEAN DEFAULT FALSE
);

CREATE INDEX ix_metadata_doggies_id ON metadata_doggies USING btree(doggie_id);
CREATE INDEX ix_metadata_is_visible ON metadata_doggies (is_visible);

