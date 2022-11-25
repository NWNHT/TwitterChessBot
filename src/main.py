
import logging
import patchworklib as pw
import time

from cardconstruction import CardConstruction
from cardplotter import CardPlotter
from DBConn import DBConn
import twitter_access as ta

def main():

    # Logging
    # Create formatter and the two handlers
    log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - %(name)s')
    f_handler = logging.FileHandler('log.log')
    s_handler = logging.StreamHandler()

    # Set the levels and formats of the handlers
    f_handler.setLevel(logging.DEBUG)
    s_handler.setLevel(logging.INFO)
    f_handler.setFormatter(log_format)
    s_handler.setFormatter(log_format)

    # Apply the handlers and logging level of the loggers
    # logger.basicConfig(handlers=[f_handler, s_handler], level=logging.DEBUG)

    # Get the logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(f_handler)
    logger.addHandler(s_handler)

    # Get database access (create if doesn't exist)
    db = DBConn('chesscom_db.db')
    # Create plotting object
    plotter = CardPlotter(db=db)
    # Create the card construction object
    cc = CardConstruction(db=db, plotter=plotter)
    # Create object to access Twitter API
    twitAPI = ta.TwitterAPI()

    # Loop until process is interrupted
    while 1:
        logger.info("-------------------- Cycle --------------------")
        responses = []
        for tweet in twitAPI.search_hashtag():
            filename = cc(tweet[1].split(' ')[0])
            responses.append((tweet[0], filename))
        
        if len(responses):
            logger.info(f"Tweeting {len(responses)} times.")
            twitAPI.reply(responses)
        else:
            logger.info("No new tweets.")
            logger.debug('debug test - __main__')

        time.sleep(30)


if __name__ == '__main__':
    main()
