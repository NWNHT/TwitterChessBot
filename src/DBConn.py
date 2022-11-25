import logging
from multiprocessing import Pool
from os.path import isfile
import pandas as pd
import plotnine as gg
import sqlite3
from stockfish import Stockfish
import time
from typing import List, Optional

import pgnproc

logger = logging.getLogger('__main__.' + __name__)

class DBConn:
	instance = None

	def __new__(cls, *args, **kwargs):
		if cls.instance == None:
			cls.instance = super().__new__(DBConn)
		return cls.instance
	
	def __init__(self, db_name: str, logging: bool = False, sf_depth: int = 15):
		self.name = db_name
		self.conn = self.connect()
		self.cursor = self.conn.cursor()

		# Initialize engine
		self.engine = Stockfish(path='/opt/homebrew/bin/stockfish')
		self.sf_depth = sf_depth
		self.engine.set_depth(self.sf_depth)
	
	def connect(self):
		"""
		Check if database exists and return cursor, if no database then create one and initialize with script.
		"""
		
		# Create db and make tables if it does not exist
		if not isfile('./chesscom_db.db'):
			try:
				self.conn = sqlite3.connect(self.name)
				self.cursor = self.conn.cursor()
				logger.info('No existing database, creating database.')
				self.create_tables()
				return self.conn
			except:
				logger.critical("Error creating database.")
				quit()
		else:
			try:
				logger.info("Connecting to database.")
				return sqlite3.connect(self.name)
			except sqlite3.Error as e:
				logger.critical("Error connecting to database.")
				quit()
	
	def __del__(self):
		self.cursor.close()
		self.conn.close()
	
	def commit(self):
		"""
		Perform commit on database
		"""

		logger.info("Committing to database.")
		self.conn.commit()

	def drop_tables(self):
		"""
		Drop all chess database tables
		"""

		with open('./SQLite_scripts/drop_tables.sql', 'r') as fh:
			commands = fh.read()

		logger.info("Dropping all tables.")
		self.cursor.executescript(commands)
		self.commit()

	def create_tables(self):
		"""
		Create all chess database tables
		"""

		with open('./SQLite_scripts/create_tables.sql', 'r') as fh:
			commands = fh.read()
		
		logger.info("Creating all tables.")
		self.cursor.executescript(commands)
		self.commit()

	def execute_command(self, command: str, arguments: Optional[tuple], commit: bool=True):
		"""
		Execute arbitrary command
		"""

		logger.debug(f"Executing command {command}.")
		if arguments is None:
			self.cursor.execute(command)
		else:
			self.cursor.execute(command, arguments)
		if commit: self.commit()

	def execute_query(self, query: str, arguments: Optional[tuple]=None):
		"""
		Execute arbitrary query
		"""

		logger.debug(f"Executing query {query}.")
		if arguments is None:
			return self.cursor.execute(query)
		else:
			return self.cursor.execute(query, arguments)

	def create_user(self, user, commit: bool=True):
		"""
		Create a user
		"""

		sql_command = "INSERT INTO User(username, account_open, last_fetched) VALUES(?,?,?)"

		logger.debug(f"Adding user {user[0]}.")
		self.cursor.execute(sql_command, user)
		if commit: self.conn.commit()

	def create_users(self, users: set, commit: bool=True):
		"""
		Create users from a set
		"""

		sql_command = "INSERT OR IGNORE INTO User(username) VALUES(?)"

		logger.debug(f"Adding users.")
		self.cursor.executemany(sql_command, users)
		if commit: self.conn.commit()
	
	def create_game(self, game: tuple, commit: bool=True):
		"""
		Create a game
		"""

		sql_command = """INSERT OR IGNORE INTO Game(game_id, white, black, white_elo, black_elo, result, occurred_at, ECO)
					     VALUES(?, (SELECT user_id FROM User WHERE username=?), (SELECT user_id FROM User WHERE username=?), ?, ?, ?, ?, ?)"""

		logger.debug(f"Adding game {game[0]} vs. {game[1]} from {game[5]}.")
		self.cursor.execute(sql_command, game)
		if commit: self.conn.commit()
	
	def create_games(self, games: List[tuple], commit: bool=True):
		"""
		Create games, create_users should be run before this to populate the User table
		"""

		sql_command = """INSERT OR IGNORE INTO Game(game_id, white, black, white_elo, black_elo, result, occurred_at, ECO)
					     VALUES(?, (SELECT user_id FROM User WHERE username=?), (SELECT user_id FROM User WHERE username=?), ?, ?, ?, ?, ?)"""

		logger.debug(f"Adding games.")
		self.cursor.executemany(sql_command, games)
		if commit: self.conn.commit()
	
	def create_positions(self, moves: List[tuple], commit: bool=True):
		"""
		Create all positions from the move list
		"""

		sql_command = """INSERT OR IGNORE INTO Position(fen, colour) VALUES(?, ?)"""

		# Condition inputs
		moves = [(x[5], x[5].split(' ')[1]) for x in moves]

		logger.debug("Adding positions to database.")
		self.cursor.executemany(sql_command, moves)
		if commit: self.commit()
	
	def create_moves(self, moves: List[tuple], commit: bool=True):
		"""
		Create all moves from move list
		"""

		sql_command = """INSERT OR IGNORE INTO Move(position_id, move_uci, move_san) VALUES((SELECT position_id FROM Position WHERE fen=?), ?, ?)"""

		# Condition inputs
		moves = [(x[5], x[2], x[3]) for x in moves]

		logger.debug("Creating moves.")
		self.cursor.executemany(sql_command, moves)
		if commit: self.commit()
	
	def create_gamemoves(self, moves: List[tuple], commit: bool=True):
		"""
		Create all of the gamemoves
		"""
		
		sql_command = """INSERT OR IGNORE INTO GameMove(game_id, move_id, move_num, clock) VALUES(?, (SELECT move_id FROM Move WHERE position_id=(SELECT position_id FROM Position WHERE fen=?) AND move_uci=?), ?, ?)"""

		# Condition inputs
		moves = [(x[0], x[5], x[2], x[1], x[4]) for x in moves]

		logger.debug("Creating game/move associations.")
		self.cursor.executemany(sql_command, moves)
		if commit: self.commit()

	def add_user_to_db(self, username: str) -> None:
		"""
		Construct lists from username and write to database
		"""

		games, users, moves = pgnproc.construct_lists_by_username(username)

		self.create_users(users, commit=False)
		self.create_games(games, commit=False)
		self.create_positions(moves, commit=False)
		self.create_moves(moves, commit=False)
		self.create_gamemoves(moves, commit=True)

	def add_pgn(self, username: str, month: str):
		"""
		Given username and month, process into lists and add to database
		"""

		games, users, moves = pgnproc.single_pgn_to_lists_by_username(username=username, month=month)

		self.create_users(users)
		self.create_games(games)
		self.create_positions(moves)
		self.create_moves(moves)
		self.create_gamemoves(moves)
	
	def change_depth(self, depth: int) -> bool:
		"""
		Set depth to specified value and return bool if value accepted
		"""

		if depth > 0 and depth < 20:
			self.sf_depth = depth
			return True
		else:
			logger.warning(f"Depth of {depth} rejected.")
			return False

	def does_game_exist_by_id(self, game_id: int) -> bool:
		"""
		Return a bool indicating if a game is in the database
		"""

		sql_query = """SELECT DISTINCT game_id
					   FROM Game
					   WHERE game_id = ?"""
		
		resp = self.cursor.execute(sql_query, (game_id,)).fetchall()

		return bool(len(resp))

	def evaluate_game_by_id(self, game_id: int, parallel: bool=False, commit: bool=True):
		"""
		Evaluate all positions from the given game_id
		"""

		sql_read_command = """	SELECT p.position_id, p.fen
								FROM Game g
								JOIN GameMove gm
								ON g.game_id = gm.game_id
								JOIN Move m
								ON gm.move_id = m.move_id
								JOIN Position p
								ON m.position_id = p.position_id
								WHERE g.game_id = ?
								  AND (eval_depth < ? or eval_depth IS NULL)
								ORDER BY move_num"""
		sql_write_command = """UPDATE Position SET eval_depth=?, first_move=?, second_move=?, third_move=?, first_move_eval=?, second_move_eval=?, third_move_eval=?, first_move_eval_type=?, second_move_eval_type=?, third_move_eval_type=? WHERE position_id = ?"""

		# Request positions without an evaluation
		self.cursor.execute(sql_read_command, (game_id, self.sf_depth))
		resp = self.cursor.fetchall()
		logger.info(f"Evaluating {len(resp)} positions at depth {self.sf_depth}.")

		# Get the evaluations
		if parallel:
			evaluations = self.eval_positions_parallel(resp)
		else:
			evaluations = self.eval_positions(resp)

		logger.debug("Done evaluating positions.")

		# Write all of the evaluations to the database
		self.cursor.executemany(sql_write_command, evaluations)
		if commit: self.commit()
	
	def evaluate_next_n_positions(self, number_of_positions: int=10, parallel: bool=False, commit: bool=True):
		"""
		Evaluate the next n positions in the database
		"""
		# TODO: Could modify query to order by eval_depth and then once all positions had been evaluated you could go through it again at a higher depth

		sql_read_command = """SELECT position_id, fen FROM Position WHERE eval_depth IS NULL LIMIT ?"""
		sql_write_command = """UPDATE Position SET eval_depth=?, first_move=?, second_move=?, third_move=?, first_move_eval=?, second_move_eval=?, third_move_eval=?, first_move_eval_type=?, second_move_eval_type=?, third_move_eval_type=? WHERE position_id = ?"""

		# Request positions without an evaluation
		self.cursor.execute(sql_read_command, (number_of_positions,))
		resp = self.cursor.fetchall()

		# Get the evaluations
		if parallel:
			evaluations = self.eval_positions_parallel(resp)
		else:
			evaluations = self.eval_positions(resp)

		logger.debug("Done evaluating positions.")

		# Write all of the evaluations to the database
		self.cursor.executemany(sql_write_command, evaluations)
		if commit: self.commit()
	
	def eval_positions(self, positions: List[tuple], commit: bool = True):
		"""
		Evaluate the given list of positions
		"""
		# TODO: Potential feature to give a single worker multiple positions to remove some of the overhead of creating the stockfish instance
		evaluations = [DBConn.evaluate_position(self.engine, pos_id, fen, self.sf_depth) for pos_id, fen in positions]
		return evaluations
	
	def eval_positions_parallel(self, positions: List[tuple], commit: bool=True):
		"""
		Evalute positions in a parallel manner using multiprocessing
		"""
		# Condition response for multiprocessing by adding depth
		positions = [(t[0], t[1], self.sf_depth) for t in positions]

		# Evaluate the positions in parallel
		with Pool() as p:
			# Start up the processes for each of the positions
			pooling = p.starmap_async(DBConn.eval_positions_parallel_helper, positions)

			# Wait for the timeout on the pool
			pooling.wait(timeout=50)
			
			# Get the evaluations or insert default 'error' response if timeout
			evaluations = [value or (1, None, None, None, None, None, None, None, None, None, positions[i][0]) for i, value in enumerate(pooling._value)]

		return evaluations

	@staticmethod
	def eval_positions_parallel_helper(position_id: int, position: str, depth: int):
		"""
		Initialize Stockfish instance for each parallel call to evaluate_position, to be used by DBConn.eval_positions_parallel
		"""
		# Initialize sf
		sf = Stockfish(path='/opt/homebrew/bin/stockfish')
		sf.set_depth(depth)

		return DBConn.evaluate_position(sf, position_id, position, depth)

	@staticmethod
	def evaluate_position(sf: Stockfish, position_id: int, position: str, depth: int):
		"""
		Helper function to evaluate a single position with Stockfish
		"""

		logger.debug(f"Position {position_id} - Start - {position}")
		# Set the board position
		sf.set_fen_position(position)

		# Evaluate top 3 moves
		top_3 = sf.get_top_moves(3)

		# Clean the response and change to preferred format
		clean_top_3 = []
		for move in top_3:
			eval_type = 'cp' if move['Centipawn'] is not None else 'mate'
			clean_top_3.append((move['Move'], 
								move['Centipawn'] or move['Mate'], 
								eval_type))

		def safe_get_tuple(lst, idx):
			"""Helper to pull from top moves list - tuple edition"""
			try:
				return lst[idx]
			except IndexError:
				return (None, None, None)

		# Create fixed size tuples for insertion into SQL command
		a = tuple(safe_get_tuple(clean_top_3, i)[0] for i in range(3))
		b = tuple(safe_get_tuple(clean_top_3, i)[1] for i in range(3))
		c = tuple(safe_get_tuple(clean_top_3, i)[2] for i in range(3))

		# Return the tuple to be inserted into SQL command
		logger.debug(f"Position {position_id} - Done  - {position}")
		return (depth, *a, *b, *c, position_id)


if __name__ == '__main__':
	# Remnants of testing

	start = time.perf_counter()

	db = DBConn('./testdb.db', sf_depth=17)

	reset_tables = False
	if reset_tables:
		db.drop_tables()
		db.create_tables()

	load_players = False
	if load_players:
		games, users, moves = pgnproc.construct_lists_by_username('girthyPolak')

		db.create_users(users)
		db.create_games(games)
		db.create_positions(moves)
		db.create_moves(moves)
		db.create_gamemoves(moves)

		games, users, moves = pgnproc.construct_lists_by_username('enieuwen')

		db.create_users(users)
		db.create_games(games)
		db.create_positions(moves)
		db.create_moves(moves)
		db.create_gamemoves(moves)

		games, users, moves = pgnproc.construct_lists_by_username('lnieuwen')

		db.create_users(users)
		db.create_games(games)
		db.create_positions(moves)
		db.create_moves(moves)
		db.create_gamemoves(moves)

		games, users, moves = pgnproc.construct_lists_by_username('NWNHT')

		db.create_users(users)
		db.create_games(games)
		db.create_positions(moves)
		db.create_moves(moves)
		db.create_gamemoves(moves)
		
	# Repeat 10 times: Get next unevaluated positins and compute
	# for _ in range(10):
	# 	db.evaluate_next_n_positions(number_of_positions=10, parallel=True)

	# Evaluate all positions from a single game
	# db.evaluate_game_by_id(game_id=5662278980, parallel=True)

	# Query to get ply numbers and evaluations from a game
	sql_query = """	SELECT p.position_id, 
				 		   CASE WHEN p.colour = 'b' THEN 2 * gm.move_num - 1
						   		WHEN p.colour = 'w' THEN 2 * gm.move_num END as ply_num,
						   CASE WHEN p.first_move_eval_type = 'mate' THEN 1000 * (p.first_move_eval)/ABS(p.first_move_eval)
						   		ELSE p.first_move_eval END as eval
					FROM Game g
					JOIN GameMove gm
					ON g.game_id = gm.game_id
					JOIN Move m
					ON gm.move_id = m.move_id
					JOIN Position p
					ON m.position_id = p.position_id
					WHERE g.game_id = ?
					ORDER BY move_num"""

	
	# resp = db.execute_query(sql_query, (5662278980,))

	# df = pd.DataFrame(resp.fetchall(), columns=['position', 'ply_num', 'eval'])

	# df.loc[df['eval'] > 1000, 'eval'] = 1000

	# print(df)

	# g = gg.ggplot(df, gg.aes(x='ply_num', y='eval')) + gg.geom_line()

	# g.draw(show=True)
	# print(db.execute_query("SELECT * FROM User").fetchall())

	del(db)

	print(f"Total time: {time.perf_counter() - start}")

