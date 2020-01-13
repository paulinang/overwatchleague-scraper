import os
import requests
import csv

class Twitch:
  '''
  Collects VODs (video on demand) using the Twitch API
  '''

  def __init__(self):
    # run `source secrets.sh` first
    self.api_url = 'https://api.twitch.tv/helix/videos'
    self.owl_twitch_id = '137512364'
    self.CLIENT_ID = os.environ['TWITCH_CLIENT_ID']
    self.CLIENT_SECRET = os.environ['TWITCH_CLIENT_SECRET']

  def get_videos(self, cursor):
    '''
    API request to get videos
    '''
    headers = { 'Client-ID': self.CLIENT_ID}
    params = {
      'user_id': self.owl_twitch_id,
      'first': 100 # Max per page
    }
    if (cursor): params['after'] = cursor
    response = requests.get(self.api_url, headers=headers, params=params)
    return response.json()

  def parse_full_match_video(self, vid_data):
    '''
    Parses a full match VOD from API data
    TODO: turn the video filter/ condition (ex. full match, non all-star only) into a callback to pass to a more generic get_videos
    '''
    title = vid_data['title']
    if (title.startswith('Full Match') and not 'All-Star Game' in title):
      # Only if video is of a full match (and not all stars)
      return {
        'title': title,
        'id': vid_data['id'],
        'url': vid_data['url']
      }

  def write_full_match_videos_to_csv(self, filename=None):
    fieldnames = ['title', 'id', 'url']
    current_cursor = None
    response = self.get_videos(current_cursor)
    videos = response['data']
    current_cursor = response['pagination'].get('cursor')

    while (current_cursor):
      response = self.get_videos(current_cursor)
      videos.extend(response['data'])
      current_cursor = response['pagination'].get('cursor')

    videos.reverse() # flip from api default so first video is oldest -> last is most recent
    if not filename:
      filename =  'twitch_fullmatch_vods.csv'
    with open(filename, 'w') as csvfile:
      # can open filename with mode 'w' to overwrite pre-existing files
      # TODO: throw error if file exists to warn of overwrite
      writer = csv.DictWriter(csvfile, fieldnames)
      for video in videos:
        parsed = self.parse_full_match_video(video)
        if parsed:
          writer.writerow(parsed)
      csvfile.close()