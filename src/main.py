
import logging
import patchworklib as pw
import time

from cardconstruction import CardConstruction
from cardplotter import CardPlotter
from DBConn import DBConn
import twitter_access as ta

if __name__ == '__main__':

    db = DBConn('chesscom_db.db')
    plotter = CardPlotter(db=db)
    cc = CardConstruction(db=db, plotter=plotter)
    twitAPI = ta.TwitterAPI()

    while 1:
        print("-------------------- Cycle --------------------")
        responses = []
        for tweet in twitAPI.search_hashtag():
            filename = cc(tweet[1].split(' ')[0])
            responses.append((tweet[0], filename))
        
        if len(responses):
            print(f"Tweeting {len(responses)} times.")
            twitAPI.reply(responses)
        else:
            print("No new tweets.")

        time.sleep(30)
    

