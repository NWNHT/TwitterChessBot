
CREATE TABLE User (
	user_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	username TEXT UNIQUE
);

CREATE TABLE Game (
	game_id INTEGER NOT NULL PRIMARY KEY,
	white INTEGER NOT NULL,
	black INTEGER NOT NULL,
	white_elo INTEGER,
	black_elo INTEGER,
	result TEXT NOT NULL,
	occurred_at TEXT,
	ECO TEXT,
	FOREIGN KEY(white) REFERENCES User(user_id),
	FOREIGN KEY(black) REFERENCES User(user_id)
);

CREATE TABLE Move (
	move_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	position_id INTEGER NOT NULL,
	move_uci TEXT,
	move_san TEXT,
	FOREIGN KEY (position_id) REFERENCES Position(position_id),
	UNIQUE (position_id, move_uci)
);

CREATE TABLE GameMove (
	game_id INTEGER NOT NULL,
	move_id INTEGER NOT NULL,
	move_num INTEGER,
	clock REAL,
	PRIMARY KEY(game_id, move_id),
	FOREIGN KEY(game_id) REFERENCES Game(game_id),
	FOREIGN KEY(move_id) REFERENCES Move(move_id)
);

CREATE TABLE Position (
	position_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	fen TEXT NOT NULL UNIQUE,
	colour TEXT NOT NULL,
	eval_depth INTEGER,
	first_move TEXT,
	first_move_eval REAL,
	first_move_eval_type TEXT,
	second_move TEXT,
	second_move_eval REAL,
	second_move_eval_type TEXT,
	third_move TEXT,
	third_move_eval REAL,
	third_move_eval_type TEXT
);

