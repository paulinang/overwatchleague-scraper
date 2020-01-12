import requests
import os.path
import csv
from datetime import datetime
from pytz import timezone
from util import check_keys

class OverwatchLeagueScraper:
  '''
  Scrape match schedule info from overwatchleague.com
  Website breaks up matches by season > stage (if available) > page and we can pull data by page
  Lists are turned into strings with elements separated by ',' in order to fix Bixby template csv import format
  '''

  def __init__(self):
    ## To get url:
    # go to https://www.overwatchleague.com/en-us/schedule
    # triggering ajax call for new page of match data by choosing another stage/week
    # inspect source > network > XHR
    # pick one of the Names that looks like "schedule?stage=1&page=1&per_page=16&season=2019" and explore header and response
    self.api_url = 'https://wzavfvwgfk.execute-api.us-east-2.amazonaws.com/production/owl/paginator/schedule'
    self.season_ref = {
      # only care about stages for the regular season (ignore preseason, alll-stars)
      '2018': {
        'stages': ['2', '3', '4', '5', '6'], # skip preseason (stage_id 1). stage 1 has stage_id 2
        'parse_match_fx': self.parse_page_matches_v1
      },
      '2019': {
        'stages': ['1', '2', '4', '5', '6'], # skip all-stars (stage_id 3)
        'parse_match_fx': self.parse_page_matches_v1
      },
      '2020': {
        'stages': ['regular_season'],
        'parse_match_fx': self.parse_page_matches_v2
      }
    }
    # keep all time in America/Los_Angeles timezone to keep things consistent
    self.timezone = timezone('America/Los_Angeles')

  def get_page_matches(self, season, stage_id, page):
    '''
    Pulls one page of match data given an season and stage
    stage_id corresponds to pagination and tabs on the owl website; does not equal the stage name (ex. stage_id 1 => stage name = preseason for 2018 season)
    '''
    headers = {
      # not having this will result in an authorization block for anoynmous user
      'referer': 'https://www.overwatchleague.com/en-us/schedule'
    }
    params = {
      'stage': stage_id,
      'page': page,
      'season': season
    }
    if season == '2020':
      params['locale'] = 'en-us'
    else:
      params['per_page'] = 30 # should exceed the possible amount of matches per page
    response = requests.get(self.api_url, headers=headers, params=params)
    return response.json()

  def parse_match_datetime(self, match, timestamp_key):
    '''
    Turns start timestamp into a date and time fo csv
    '''
    start_timestamp = match.get(timestamp_key)
    start_dt_object = date = time = None
    if start_timestamp:
      start_dt_object = datetime.fromtimestamp(start_timestamp/1000, self.timezone)
      date = start_dt_object.strftime('%m/%d/%Y')
      time = start_dt_object.strftime('%H:%M')
    return { 'start_timestamp': start_timestamp, 'date': date, 'time': time }

  def parse_page_matches_v1(self, season, page_matches):
    '''
    Parses response of get_page_matches into an array of dictionaries with match info
    For v1 matches (from earlier seasons 2018 & 2019)
    '''
    if check_keys(page_matches, 'content', 'tableData', 'data', 'matches'):
      data = page_matches['content']['tableData']['data']
    else:
      raise AttributeError('No data available in page_matches')

    # get event host/ venue info
    homestand = data.get('events', {}).get('homestand', {}) or {}
    host = homestand.get('hostTeamshortName')
    venue_name = homestand.get('location', {}).get('name', 'Blizzard Arena').replace('Tickets |', '').strip()
    parsed = []
    for match in data['matches']:
      # get date/time info
      dt_info = self.parse_match_datetime(match, 'startDateTS')
      # get competitor & score info
      competitors = match.get('competitors')
      teams = scores = None
      if competitors and len(competitors) == 2:
        if not competitors[0].get('abbreviatedName') or not competitors[0].get('abbreviatedName'):
          raise AttributeError('Missing abbreviated competitor name')
        else:
          teams = ','.join([competitors[0].get('abbreviatedName'), competitors[1].get('abbreviatedName')])
          scores = ','.join([str(competitors[0].get('score')), str(competitors[1].get('score'))])
      # build and append object for match info to parsed list
      parsed.append({
        'id': match.get('id'),
        'season': season,
        'stage': data.get('stage', '').replace('stage', '').strip(),
        'page_name': data.get('name'),
        # these are not supported in v1, but we add them for consistency with v2
        'host': host,
        'venue_name': venue_name,
        'venue_address': None,
        'venue_link': None,
        # these are in US/Los_Angeles timezone to stay consistent
        'start_timestamp': dt_info.get('start_timestamp'),
        'date': dt_info.get('date'),
        'time': dt_info.get('time'),
        'status': match.get('status'),
        # "item1,item2" is the format needed to indicate an array for Bixby template csv import
        'teams': teams,
        'scores': scores
      })
    return parsed

  def parse_page_matches_v2(self, season, page_matches):
    '''
    Parses response of get_page_matches into an array of dictionaries with match info
    For v2 matches (starting 2020)
    '''
    if check_keys(page_matches, 'content', 'tableData', 'events'):
      data = page_matches['content']['tableData']
    else:
      raise AttributeError('No data available in page_matches')

    parsed = []
    for event in data['events']:
      # get event host/ venue info
      event_info = event.get('eventBanner') or {}
      host = venue_name = venue_address = venue_link = None
      if event_info.get('hostingTeam'):
        host = event_info['hostingTeam'].get('shortName')
      if event_info.get('venue'):
        venue_name = event_info['venue'].get('title')
        venue_address = event_info['venue'].get('location')
        venue_link = event_info['venue'].get('link', {}).get('href')
      for match in event['matches']:
        # get date/time info
        dt_info = self.parse_match_datetime(match, 'startDate')
        # get competitor info
        teams = None
        if match.get('competitors') and len(match['competitors']) == 2:
          if (not match['competitors'][0].get('abbreviatedName') or not match['competitors'][0].get('abbreviatedName')):
            raise AttributeError('Missing abbreviated competitor name')
          else:
            teams = ','.join([match['competitors'][0].get('abbreviatedName'), match['competitors'][1].get('abbreviatedName')])
        # get score info
        scores = None
        if match.get('scores') and len(match['scores']) == 2:
          scores = ','.join([str(match['scores'][0]), str(match['scores'][1])])
        else:
          scores = '0,0'

        parsed.append({
          'id': match.get('id'),
          'season': season,
          'stage': 'regular_season', # 2020 season doesn't have stages
          'page_name': data.get('name'),
          'host': host,
          'venue_name': venue_name,
          'venue_address': venue_address,
          'venue_link': venue_link,
          # these are in US/Los_Angeles timezone to stay consistent
          'start_timestamp': dt_info.get('start_timestamp'),
          'date': dt_info.get('date'),
          'time': dt_info.get('time'),
          'status': match.get('status'),
          # "item1,item2" is the format needed to indicate an array for Bixby template csv import
          'teams': teams,
          'scores': scores
        })
    return parsed

  def write_stage_matches_to_csv(self, season, stage_id, filename=None):
    '''
    Writes all stage matches into a csv
    Gets matches from website page by page, parses matches, and writes to csv file
    '''

    fieldnames = [
      'id', 'season', 'stage', 'page_name',
      'host', 'venue_name', 'venue_address', 'venue_link',
      'start_timestamp', 'date', 'time', 'status', 'teams', 'scores'
    ]
    page = 1 # this is how the website starts page count
    total_pages = 1 # so we always get first page

    while (page <= total_pages):
      response = self.get_page_matches(season, stage_id, page)
      parsed = self.season_ref[season]['parse_match_fx'](season, response)
      if 'data' in response['content']['tableData']:
        stage = '_'.join([season, response['content']['tableData']['data']['stage']]) + '.csv'
      else:
        stage = stage_id

      if not filename:
        # we didn't give a specific file to append to, create a filename based on season + stage
        filename = '_'.join([season, stage]) + '.csv'
      file_exists = os.path.isfile(filename)

      with open(filename, 'a') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames)
        if not file_exists:
          writer.writeheader()
        for match in parsed:
          writer.writerow(match)
      csvfile.close()
      total_pages = response['content']['tableData']['pagination']['totalPages']
      page += 1

  def write_season_matches_to_csv(self, season, filename=None):
    '''
    Write all season matches into a csv
    '''
    if not filename:
      filename = season + '.csv'
    print('Writing matches for Overwatch League season %s to %s...' % (season, filename))

    for stage_id in self.season_ref[season]['stages']:
      self.write_stage_matches_to_csv(season, stage_id, filename)
    print ('write_season_matches_to_csv complete!')