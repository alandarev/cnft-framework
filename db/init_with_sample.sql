CREATE EXTENSION pgcrypto;

DROP TABLE IF EXISTS doggies;
CREATE TABLE doggies(
	id SERIAL,
        minting_id INT UNIQUE,
	key UUID DEFAULT gen_random_uuid(),
        price INT UNIQUE,
        tier INT NOT NULL,
        is_sold BOOLEAN DEFAULT FALSE,
        is_sent BOOLEAN DEFAULT FALSE,
        collected INT,
	reserved_until TIMESTAMP,
        reserve_hash VARCHAR,
        doggie_id INT UNIQUE,
	doggie_metadata JSON NOT NULL,
	doggie_image VARCHAR NOT NULL
);

CREATE INDEX ix_doggies_id ON doggies USING btree(id);
CREATE INDEX ix_doggies_price ON doggies (price);
CREATE INDEX ix_doggies_key ON doggies USING hash(key);
CREATE INDEX ix_doggies_tier ON doggies (tier);
CREATE INDEX ix_doggies_reserved_until ON doggies ((reserved_until::TIMESTAMP));
CREATE INDEX ix_doggies_is_sold ON DOGGIES ((is_sold::BOOLEAN));
CREATE INDEX ix_doggies_is_sent ON DOGGIES ((is_sent::BOOLEAN));
CREATE INDEX ix_doggies_meta_id ON doggies USING btree(doggie_id);

CREATE OR REPLACE FUNCTION check_atomic_reserve()
  RETURNS TRIGGER AS
$BODY$
BEGIN
  IF (NEW.reserve_hash IS DISTINCT FROM OLD.reserve_hash) AND (OLD.reserve_hash IS NOT NULL) AND (OLD.reserved_until > NOW())
  THEN
      RAISE EXCEPTION 'Is already reserved';
  END IF;
  RETURN NEW;
END;
$BODY$ LANGUAGE PLPGSQL;

CREATE TRIGGER trigger_check_atomic_reserve
BEFORE UPDATE OF "reserve_hash"
  ON "doggies"
FOR EACH ROW
EXECUTE PROCEDURE check_atomic_reserve();

INSERT INTO doggies (price, doggie_id, doggie_metadata, doggie_image, tier) VALUES (10000000+floor(RANDOM()*100000000)::int, 1020, '{ "721":{ "7724da6519bbdda506e4d8acce11e01e01019726ddf017418f9c958a": { "CryptoDoggie1020": { "id": 1020, "name": "Crypto Doggie #1020", "image": "ipfs://ipfs/QmQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41", "breed": "Shiba", "composition": { "dog": { "body": "normal", "head": "normal", "eyes": "wink", "mouth": "smile" }, "background": "none", "equipment": { "straight_hand": "flag_cardano", "legs": "shorts_denim", "feet": "sneakers_green", "arced_hand": "hand_in_hoodie_red", "body": "hoodie_red" } } } } } }', 'mQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41', 0);
INSERT INTO doggies (price, doggie_id, doggie_metadata, doggie_image, tier) VALUES (10000000+floor(RANDOM()*100000000)::int, 1025, '{ "721":{ "7724da6519bbdda506e4d8acce11e01e01019726ddf017418f9c958a": { "CryptoDoggie1020": { "id": 1025, "name": "Crypto Doggie #1025", "image": "ipfs://ipfs/QmQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41", "breed": "Shiba", "composition": { "dog": { "body": "normal", "head": "normal", "eyes": "wink", "mouth": "smile" }, "background": "none", "equipment": { "straight_hand": "flag_cardano", "legs": "shorts_denim", "feet": "sneakers_green", "arced_hand": "hand_in_hoodie_red", "body": "hoodie_red" } } } } } }', 'mQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41', 0);
INSERT INTO doggies (price, doggie_id, doggie_metadata, doggie_image, tier) VALUES (10000000+floor(RANDOM()*100000000)::int, 1035, '{ "721":{ "7724da6519bbdda506e4d8acce11e01e01019726ddf017418f9c958a": { "CryptoDoggie1020": { "id": 1035, "name": "Crypto Doggie #1035", "image": "ipfs://ipfs/QmQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41", "breed": "Shiba", "composition": { "dog": { "body": "normal", "head": "normal", "eyes": "wink", "mouth": "smile" }, "background": "none", "equipment": { "straight_hand": "flag_cardano", "legs": "shorts_denim", "feet": "sneakers_green", "arced_hand": "hand_in_hoodie_red", "body": "hoodie_red" } } } } } }', 'mQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41', 0);
INSERT INTO doggies (price, doggie_id, doggie_metadata, doggie_image, tier) VALUES (10000000+floor(RANDOM()*100000000)::int, 1045, '{ "721":{ "7724da6519bbdda506e4d8acce11e01e01019726ddf017418f9c958a": { "CryptoDoggie1020": { "id": 1045, "name": "Crypto Doggie #1045", "image": "ipfs://ipfs/QmQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41", "breed": "Shiba", "composition": { "dog": { "body": "normal", "head": "normal", "eyes": "wink", "mouth": "smile" }, "background": "none", "equipment": { "straight_hand": "flag_cardano", "legs": "shorts_denim", "feet": "sneakers_green", "arced_hand": "hand_in_hoodie_red", "body": "hoodie_red" } } } } } }', 'mQnhGA8HDu7CJu3ymk9NWzRFPZxoPP1qXt1dV58fj9j41', 0);
