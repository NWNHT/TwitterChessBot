
import os
from typing import List, Optional

import dotenv
import tweepy as tp

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)

class TwitterAPI:

    def __init__(self):
        
        # Consumer tokens
        self.API_key = os.environ.get('TWITTER_CONSUMER_API_KEY')
        self.API_secret = os.environ.get('TWITTER_CONSUMER_API_SECRET')

        # Access tokens
        self.access_token = None
        self.access_token_secret = None

        # Authorization and api objects
        self.auth = None
        self.api = None

        # Search
        self.label = 'Testing'
        self.query = '#chessindata'
        self.maxResults = 10

        # Test
        self.latest_responded = 0

        # Initialize authorization of the twitter API
        self.get_auth()
        self.init_latest()
    
    def get_auth(self):
        """
        Use tokens in the environment or get user to auth using pin auth
        """
        if os.environ.get('TWITTER_ACCESS_TOKEN') is None or os.environ.get('TWITTER_ACCESS_TOKEN_SECRET') is None:
            print("Authorize using pin auth.")
            self.twitter_pin_auth()
        else:
            print("Tokens already present")
            self.access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
            self.access_token_secret = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
            
        self.auth = tp.OAuth1UserHandler(consumer_key=self.API_key, 
                                         consumer_secret=self.API_secret,
                                         access_token=self.access_token,
                                         access_token_secret=self.access_token_secret)

        # Create api object for interactions with Twitter, re-authing and retrying if unsuccessful
        try:
            self.api = tp.API(self.auth)
            self.api.verify_credentials()
        except:
            print("Initial authorization failed, re-authorize using pin auth.")
            # This situation might arise if there are tokens in environment but they are invalid
            self.twitter_pin_auth()
            self.auth = tp.OAuth1UserHandler(consumer_key=self.API_key, 
                                             consumer_secret=self.API_secret,
                                             access_token=self.access_token,
                                             access_token_secret=self.access_token_secret)
            self.api = tp.API(self.auth)

    def twitter_pin_auth(self):
        """
        Complete the pin auth procedure
        """
        # Begin auth
        auth = tp.OAuth1UserHandler(self.API_key,
                                    self.API_secret,
                                    callback='oob')

        # Have user enter pin
        print(auth.get_authorization_url())
        verif = input("Input PIN: ")
        self.access_token, self.access_token_secret = auth.get_access_token(verif)
        
        # Write the token and secret to .env
        dotenv.set_key(dotenv_file, 'TWITTER_ACCESS_TOKEN', self.access_token)
        dotenv.set_key(dotenv_file, 'TWITTER_ACCESS_TOKEN_SECRET', self.access_token_secret)

    def init_latest(self):
        """
        Update the latest responded field, to be used on startup
        """
        latest = self.search_hashtag()[0]
        self.latest_responded = latest[0]
        # self.latest_responded = 1595546697018802176 # testing value

    def search_hashtag(self):
        """
        Search twitter for recent tweets
        """

        try:
            results = self.api.search_30_day(self.label,
                                             query=self.query,
                                             maxResults=self.maxResults)
            # print(f"Found {len(results)} tweets.")
        except Exception as e:
            print(f"Error querying latest tweets: {e}")
            quit()
        
        tweets = []
        for tweet in results:
            if tweet.id > self.latest_responded:
                tweets.append((tweet.id, tweet.text, tweet.created_at))
        
        return tweets
    
    def reply(self, replies: List[tuple]):
        """
        Reply to all tweets given in replies list
        List[(id, filename)]
        """

        for reply in replies:
            print(f"For tweet: {reply}")
            media = self.api.media_upload(reply[1])
            # media = self.api.media_upload('./cards/44672402709.png')

            self.api.update_status("Test reply with api", 
                                   in_reply_to_status_id=reply[0], 
                                   media_ids=[media.media_id], 
                                   auto_populate_reply_metadata=True)
        
        # Update the latest replied
        self.latest_responded = replies[0][0]
        
        print("Done replying")
