import requests
import os.path
import csv
from datetime import datetime
from pytz import timezone

class OverwatchLeagueScraper:
  # Only works for season 2018 and 2019 of overwatch league (2020 schedule is only available as a graphic pdf)
  # overwatchleague.com breaks up matches by season > stage > page and we can pull data by page

  def __init__(self):
    ## To get url:
    # go to https://www.overwatchleague.com/en-us/schedule
    # triggering ajax call for new page of match data by choosing another stage/week
    # inspect source > network > XHR
    # pick one of the Names that looks like "schedule?stage=1&page=1&per_page=16&season=2019" and explore header and response
    self.api_url = 'https://wzavfvwgfk.execute-api.us-east-2.amazonaws.com/production/owl/paginator/schedule'

    # keep all time in America/Los_Angeles timezone to keep things consistent
    self.timezone = timezone('America/Los_Angeles')

  def get_page_matches(self, season, stage_idx, page):
    # Pulls one page of match data given an season and stage
    # stage_idx corresponds to pagination and tabs on the owl website; does not equal the stage name (ex. stage_idx 1 => stage name = preseason for 2018 season)

    headers = {
      # not having this will result in an authorization block for anoynmous user
      'referer': 'https://www.overwatchleague.com/en-us/schedule'
    }
    params = {
      'stage': stage_idx,
      'page': page,
      'per_page': 30, # should exceed the possible amount of matches per page
      'season': season
    }

    response = requests.get(self.api_url, headers=headers, params=params)
    return response.json()

  def parse_page_matches(self, season, page_matches,):
    # Parses response of get_page_matches into an array of dictionaries with match info
    # Currently set up to create values that would fit the format needed for Bixby template csv imports
    data = page_matches['content']['tableData']['data']
    parsed = []
    for match in data['matches']:
      start_timestamp = match['startDateTS']/1000
      start_dt_object = datetime.fromtimestamp(start_timestamp, self.timezone)
      current = {
        'id': match['id'],
        'season': season,
        'stage': data['stage'].replace('stage', '').strip(),
        'page_name': data['name'],
        # these are in US/Los_Angeles timezone to stay consistent
        'date': start_dt_object.strftime('%m/%d/%Y'),
        'time': start_dt_object.strftime('%H:%M'),
        'status': match['status'],
        # "item1,item2" is the format needed to indicate an array for Bixby template csv import
        'teams': ','.join([match['competitors'][0]['abbreviatedName'], match['competitors'][1]['abbreviatedName']]),
        'scores': ','.join([str(match['competitors'][0]['score']), str(match['competitors'][1]['score'])])
      }
      parsed.append(current)
    return parsed

  def write_stage_matches_to_csv(self, season, stage_idx, filename):
    # Writes all stage matches into a csv by getting matches page by page, parsing matches, and writing to csv file

    fieldnames = ['id', 'season', 'stage', 'page_name',  'date', 'time', 'status', 'teams', 'scores']
    page = 1 # this is how the website starts page count
    total_pages = 1 # so we always get first page

    while (page <= total_pages):
      response = self.get_page_matches(season, stage_idx, page)
      parsed = self.parse_page_matches(season, response)
      if not filename:
        # we didn't give a specific file to append to, create a filename based on season + stage
        filename = '_'.join([season, response['content']['tableData']['data']['stage']]) + '.csv'
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

if __name__ == '__main__':
  # running `python scaper.py` will create files for the 2018 and 2019 OWL seasons
  scraper = OverwatchLeagueScraper()
  regular_stage_idx = {
    # only care about stages for the regular season (ignore preseason, alll-stars)
    '2018': ['2', '3', '4', '5', '6'], # skip preseason (stage_idx 1). stage 1 has stage_idx 2
    '2019': ['1', '2', '4', '5', '6'] # skip all-stars (stage_idx 3)
  }
  print('Scraping regular stage matches for Overwatch League season 2018 & 19...')
  for season in regular_stage_idx.keys():
    print('Getting season %s matches' % season)
    for stage_idx in regular_stage_idx[season]:
      print('stage_idx: %s' % stage_idx)
      scraper.write_stage_matches_to_csv(season, stage_idx, season + '.csv')
  print('Done!')