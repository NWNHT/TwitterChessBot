
# A collection of functions to create a dataframe from a pgn and write to and read from parquet files

import asyncio
import chess
import chess.pgn
import io
import os
from pathlib import Path
import re
from typing import Coroutine, Dict, List, Optional, Set, Tuple

from chessdotcom.aio import ChessDotComError, Client, get_player_game_archives, get_player_games_by_month_pgn, get_player_stats


read_size = 1000000
global_pgn_directory = str(Path(__file__).parent.parent) + "/pgns/"

Client.rate_limit_handler.retries = 4
Client.rate_limit_handler.tts = 2

# These functions are used in order to request pgn files from chess.com for a given list of usernames


async def gather_cors(cors: List[Coroutine]):
    """Run gather for given list of coroutines, return result"""
    responses = await asyncio.gather(*cors)
    return responses


async def save_player_games_by_month(username: str, year: str, month: str, pgn_directory: str = global_pgn_directory) -> None:
    """Wrapper for get_player_games_by_month_pgn that saves the pgns directly to an appropriate directory.  It is assumed that the username directory exists."""
    filepath = f"{pgn_directory}{username}/{year}-{month}.txt"
    # This is an exceptionally bad handling of the possibility of a 429 error from chess.com, has worked so far though
    try:
        print(f"Start file {year}-{month} for {username}.")
        data = await get_player_games_by_month_pgn(username=username, year=year, month=month)
    except ChessDotComError:
        print(f"Failure on {year}-{month} for {username}.  Trying again.")
        data = await get_player_games_by_month_pgn(username=username, year=year, month=month)

    # Write the result to appropriate file
    with open(filepath, 'w') as fh:
        fh.write(data.text)
    print(f"Wrote file {year}-{month} for {username}.")


def make_player_games_by_month_coro(requests: Dict[str, Dict]) -> List[Coroutine]:
    """Given requests dictionary, make coroutines for all dates"""
    cors = []
    for username, response in requests.items():
        cors.extend([save_player_games_by_month(username, response["Dates"][i][:4], response["Dates"][i][-2:]) for i in range(len(response["Dates"]))])
        make_directory(username=username, pgn_directory=global_pgn_directory)
    
    return cors


def alt_make_queries(coro: List[Coroutine]) -> None:
    """Given list of coroutines, run them all, no return"""
    asyncio.run(gather_cors(coro))


def get_player_months(usernames: List["str"]) -> Dict[str, Dict[str, List[str]]]:
    """Get a list of the month archives of a player by username"""
    cors = [get_player_game_archives(name) for name in usernames]
    responses = asyncio.run(gather_cors(cors))

    return {username: {"Dates": [response.json['archives'][i][-7:].replace("/", "-") for i in range(len(response.json['archives']))]} for username, response in zip(usernames, responses)}


def get_dates_not_downloaded(responses: Dict[str, Dict[str, List[str]]], pgn_directory: str = global_pgn_directory) -> Dict[str, Dict[str, List[str]]]:
    """Diff the dates given by archives and the dates of files already downloaded, return dict of lists of dates to be requested"""
    for username, response in responses.items():
        if os.path.exists(pgn_directory + username) and os.listdir(pgn_directory + username): # If path exists and is not empty
            # Make the list of archives into set and difference to the existing files.
            # This results in just the archive dates that aren't present in the directory
            # - With a bonus of including the latest month so as to get the current month games
            # - This line spits in the face of readability
            responses[username]["Dates"] = list(set(response["Dates"]).difference(set(list(map(lambda x: x[:7], os.listdir(pgn_directory + username))))).union(set([response["Dates"][-1]])))
    
    return responses


def get_specified_dates(responses: Dict[str, Dict[str, List[str]]], months: List[str], pgn_directory: str = global_pgn_directory) -> Dict[str, Dict[str, List[str]]]:
    """Filter for only requested months in format List['yyyy-mm']"""
    for username, response in responses.items():
        # Create an intersection of the available dates and the provided dates/months, then add the latest month
        responses[username]["Dates"] = list(set(response["Dates"]).intersection(set(months)).union(set([response["Dates"][-1]])))
    
    return responses


def make_directory(username: str, pgn_directory: str = global_pgn_directory) -> None:
    if not os.path.exists(pgn_directory + username):
        os.mkdir(pgn_directory + username)


def make_queries(requests: Dict[str, Dict], pgn_directory: str = global_pgn_directory) -> Dict[str, Dict]:
    """Compete the coroutines and save to their respective files"""
    for username, data in requests.items():
        requests[username]["PGNs"] = asyncio.run(gather_cors(data["Coroutines"]))
        requests[username]["PGNs"] = [x.text for x in requests[username]["PGNs"]]
        for date, pgn in zip(data["Dates"], data["PGNs"]):
            make_directory(username, pgn_directory=pgn_directory)
            with open(f"{pgn_directory}{username}/{date}.txt", 'w') as fh:
                fh.write(pgn)
        print(f"Completed requests for {username}.")
    return requests


def download_by_username_list_and_month_list_better(usernames: List[str], months: List[str]) -> None:
    """Given list of usernames and months will download and save to file async"""
    
    response = get_player_months(usernames)
    response = get_specified_dates(response, months)
    coro = make_player_games_by_month_coro(requests=response)
    alt_make_queries(coro=coro)


# The functions below are used to go from pgn to a dataframe, optionally saved as a parquet file, then the data can be read from the files


def pgn_to_gamelist(pgn: str) -> list:
    """Take a pgn string and return a list containing a list of dictionaries containing the game information."""
    # Compile re expressions to detect header information and individual moves
    header = re.compile(r'\[(.*?) \"(.*?)\"\]')
    moves = re.compile(r'([0-9]*[.]+) ([a-zA-Z0-9+#=/-]*) \{\[%clk ([0-9:.]*)\]\}')

    # Split pgn into games and prep loop
    raw_game_list = pgn.split('\n\n\n')
    game_list = []

    # Loop through games in pgn list, make dictionaries of headers, original pgn, and a list of tuples of moves
    for game in raw_game_list:
        game_list.append(dict(header.findall(game)))
        game_list[-1]["pgn"] = game
        game_list[-1]['moves'] = moves.findall(game)
    
    return game_list


def pgn_to_moves(game: str) -> List[tuple]:
    """Take a pgn as string and return list of tuples describing the moves"""
    # Read game from string
    fh = io.StringIO(game)
    game_obj = chess.pgn.read_game(fh)

    # Set up return objects
    movelist = []
    game_id = game_obj.headers["Link"].split('/')[-1]

    while not game_obj.is_end():
        # Iterate move
        game_obj = game_obj.next()

        # Extract information
        movenum = (game_obj.ply() + 1)  // 2
        uci = game_obj.uci()
        san = game_obj.san()
        clock = game_obj.clock()
        position = game_obj.board().fen().rsplit(' ', 2)[0]

        # Construct tuples and add to lists
        movelist.append((game_id, movenum, uci, san, clock, position))
    
    return movelist


def pgn_to_db_lists(pgn: str) -> Tuple[List[tuple], Set[list], List[tuple]]:
    """Take a pgn string and return two lists containing the information to be put in the database."""
    # Compile re expressions to detect header information and individual moves
    header = re.compile(r'\[(.*?) \"(.*?)\"\]')

    # Split pgn into games and prep loop
    raw_game_list = pgn.split('\n\n\n')
    gamelist = []
    userlist = set()
    movelist = []

    # Loop through games in pgn list, make dictionaries of headers, add to userlist and gamelist
    for game in raw_game_list:
        headers = dict(header.findall(game))
        userlist.update(((headers['White'],), (headers['Black'],)))
        gamelist.append((headers['Link'].split('/')[-1],headers['White'], headers['Black'], headers['WhiteElo'], headers['BlackElo'], headers['Result'], headers['UTCDate'].replace('.', '-') + ' ' + headers['UTCTime'], headers.get('ECO', 'Unknown')))
        movelist.extend(pgn_to_moves(game))
    
    return gamelist, userlist, movelist


def construct_lists_by_username(username: str, base_directory_name: str=global_pgn_directory) -> Tuple[List[tuple], Set[list], List[tuple]]:
    """Construct gamelist, userlist and movelist for the given user"""
    pgn_directory_name = base_directory_name + username + "/"
    gamelist = []
    userlist = set()
    movelist = []
	# For each file, read and create a list of games and users
    for file in os.listdir(pgn_directory_name):
        if file[-4:] == ".txt":
            with open(pgn_directory_name + file) as fh:
                data = fh.read(read_size)
            games, users, moves = pgn_to_db_lists(data)
            gamelist.extend(games)
            userlist.update(users)
            movelist.extend(moves)

    return gamelist, userlist, movelist

def single_pgn_to_lists_by_username(username: str, month: str, base_directory_name: str=global_pgn_directory) -> Tuple[List[tuple], Set[list], List[tuple]]:
    """
    Read a single pgn and construct lists to insert into the database
    """

    filepath = base_directory_name + username + "/" + month + '.txt'
    gamelist = []
    userlist = set()
    movelist = []
	# For each file, read and create a list of games and users
    
    try:
        with open(filepath) as fh:
            data = fh.read(read_size)
        games, users, moves = pgn_to_db_lists(data)
        gamelist.extend(games)
        userlist.update(users)
        movelist.extend(moves)
    except FileExistsError:
        print("File Exists Error while reading pgn.")
        quit()

    return gamelist, userlist, movelist


if __name__ == "__main__":

    usernames = ["NWNHT"]

    # Below is the flow of giving the username to saving the data
    # All of these are susceptible to failure by HTTP code 429 for exceeding the API limit

    # This creates a large dictionary out of the responses(async) and then loops through and saves them
    # response = get_player_months(usernames)
    # response = get_dates_not_downloaded(response, pgn_directory="./../../pgns/")
    # response = create_archive_requests(response)
    # response = make_queries(response, pgn_directory="./../../pgns/")

    # Or

    # download_by_username_list(usernames) # Just calls the functions above in order
    
    # Or

    # This fetches and saves month archives in a 'single step'(async)
    # response = get_player_months(usernames)
    # response = get_dates_not_downloaded(response, pgn_directory="./../../pgns/")
    # coro = make_player_games_by_month_coro(requests=response)
    # alt_make_queries(coro=coro)

    # Or

    # download_by_username_list_better(usernames=usernames)
