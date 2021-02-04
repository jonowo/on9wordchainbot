CREATE TABLE player (
    id SERIAL,
    user_id BIGINT PRIMARY KEY,
    game_count INTEGER NOT NULL,
    win_count INTEGER NOT NULL,
    word_count INTEGER NOT NULL,
    letter_count INTEGER NOT NULL,
    longest_word TEXT
);

CREATE TABLE game (
    id SERIAL,
    group_id BIGINT NOT NULL,
    players INTEGER NOT NULL,
    game_mode TEXT NOT NULL,
    winner BIGINT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    PRIMARY KEY (group_id, start_time)
);

CREATE TABLE gameplayer (
    id SERIAL,
    user_id BIGINT NOT NULL,
    group_id BIGINT NOT NULL,
    game_id INTEGER NOT NULL,
    won BOOLEAN NOT NULL,
    word_count INTEGER NOT NULL,
    letter_count INTEGER NOT NULL,
    longest_word TEXT,
    PRIMARY KEY (user_id, game_id)
);

CREATE TABLE donation (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    donation_id TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    donate_time TIMESTAMP NOT NULL,
    telegram_payment_charge_id TEXT NOT NULL,
    provider_payment_charge_id TEXT NOT NULL
);

CREATE TABLE wordlist (
    word TEXT NOT NULL,
    accepted BOOLEAN NOT NULL,
    reason TEXT
);
