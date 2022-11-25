
import logging
import pandas as pd
import patchworklib as pw
import requests
from typing import Tuple

from cardplotter import CardPlotter
from DBConn import DBConn
import pgnproc
import twitter_access as ta

class CardConstruction:
    """
    Request, store, process, store, and plot data from chess.com, specified by game_id
    """
    
    def __init__(self, db: DBConn, plotter: CardPlotter) -> None:
        
        # It only makes sense for the CardPlotter to use the same database as CardConstruction
        self.db = db
        self.plotter = plotter

        self.game_id = None
        self.details_url_base = "https://www.chess.com/callback/live/game/"

    def __call__(self, game_id: int):
        """
        Take the game_id, orchestrate the whole retrieval and output
        """
        self.game_id = game_id
        print(f"Generating for game: {self.game_id}")

        # Check if game_id is in the database
        if not self.db.does_game_exist_by_id(self.game_id):
            print("Game not in database")

            # Get the game details for requesting data
            username, month = self._get_game_details()

            # Download the month archieve for the player
            self._download_month_archieve(username, month)

            # Add the games from the pgn to the database
            self._add_archieve_to_db(username, month)
        else:
            print("Game present")
        
        # Evaluate game
        self._evaluate_game()

        # Generate card
        return self._generate_card()


    def _get_game_details(self) -> Tuple[str, str]:
        """
        Send request to chess.com for game details
        - Return username and date to be retrieved
        """

        try:
            json_resp = requests.get(self.details_url_base + str(self.game_id)).json()
        except Exception as e:
            logging.error(f"Error requesting game data from Chess.com: {e}")
            quit()

        # Extract the players and date from game details
        white_username = json_resp['game']['pgnHeaders']['White']
        # black_username = json_resp['game']['pgnHeaders']['Black']
        game_date      = json_resp['game']['pgnHeaders']['Date'][:7].replace('.','-')

        # TODO: Could potentially check whihch user has played fewer games and pass along that user, for now just pass white

        return white_username, game_date

    def _download_month_archieve(self, user: str, month: str) -> None:
        """
        Access chess.com api for month archieve, save pgn file to directory
        """

        # Download the pgns
        try:
            pgnproc.download_by_username_list_and_month_list_better([user], [month])
        except Exception as e:
            print(e)
            logging.error(f"Error requesting pgns: {e}")
            quit()
    
    def _add_archieve_to_db(self, username: str, month: str):
        """
        Add recently downloaded pgn to database, or all pgns for a user?  This may require additions to DBConn
        """

        self.db.add_pgn(username, month)

    def _evaluate_game(self):
        """
        Evaluate game positions using DBConn
        """

        self.db.evaluate_game_by_id(game_id=self.game_id, parallel=True)

    def _generate_card(self):
        """
        Call the plotter to generate the card and output
        """

        return self.plotter.gen_card(game_id=self.game_id)


if __name__ == '__main__':
    # A bunch of testing remnants

    # Model setup
    db = DBConn('testdb.db', logging=True)
    plotter = CardPlotter(db=db)
    cc = CardConstruction(db=db, plotter=plotter)

    cc(11315693285)

    quit()

    twitter_access = ta.TwitterAPI()
    twitter_access.get_auth()
    # print(twitter_access.search_hashtag())

    responses = []
    tweets = twitter_access.search_hashtag()
    for tweet in tweets:
        filename = cc(tweet[1].split(' ')[0])
        responses.append((tweet[0], filename))
    
    twitter_access.reply(responses)
        




