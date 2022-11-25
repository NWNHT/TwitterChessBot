
import argparse
import logging
import patchworklib as pw
import time

from cardconstruction import CardConstruction
from cardplotter import CardPlotter
from DBConn import DBConn
import twitter_access as ta

def main(args):

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

    # Get the logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(f_handler)
    logger.addHandler(s_handler)


    # Get database access (create if doesn't exist)
    db = DBConn('chesscom_db.db', sf_depth=args.default_depth)
    # Create plotting object
    plotter = CardPlotter(db=db)
    # Create the card construction object
    cc = CardConstruction(db=db, plotter=plotter)
    # Create object to access Twitter API
    twitAPI = ta.TwitterAPI(max_tweet_results=args.max_tweet_results)

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

        time.sleep(int(args.poll_period))

def parse_arguments():
    """
    Parse the command-line arguments
    """

    parser = argparse.ArgumentParser(prog='TwitterChessBot',
                                     description='A bot to scan #chessindata and respond with an infographic.')
    
    # This should be between 1 and 20, this is enforced by DBConn
    parser.add_argument('-d',
                        '--default_depth',
                        help='set default evaluation depth in moves - Default: 15 - Range: [1, 20]',
                        action='store',
                        default=15)
    
    # Anything less than 30s is probably overkill, this is not enforced/checked anywhere
    parser.add_argument('-p',
                        '--poll_period',
                        help='set period of the Twitter poll in seconds - Default: 30 - Range: [30, inf)',
                        action='store',
                        default=30)

    # This must be between 10 and 100 inclusive, anything beyond this range will cause a Twitter API error
    parser.add_argument('-m',
                        '--max_tweet_results',
                        help='set maximum tweets pulled in a request - Default: 10 - Range: [10, 100]',
                        action='store',
                        default=10)
    
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()

    main(args)
