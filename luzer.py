#!/usr/bin/env python3
import os
import datetime
import pytz
from collections import namedtuple
import json
import sys

import recurring_ical_events
import icalendar
import requests
import urllib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ['https://www.googleapis.com/auth/calendar']


def localize_datetime(dtime):
    timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    tz_offset = timezone.utcoffset(dtime)
    return dtime + tz_offset


class ICal():
    def __init__(self, ical):
        self._ical = ical
    
    @classmethod
    def from_url(cls, url):
        ical_string = urllib.request.urlopen(url).read()
        return cls(icalendar.Calendar.from_ical(ical_string))

    def get_ical_events(self, dates=None):
        if dates is None:
            for event in recurring_ical_events.of(self._ical):
                yield event
        else:
            for event in recurring_ical_events.of(self._ical).between(*dates):
                yield event

    def get_luzer_events(self, dates=None):
        def parse_datetime(dt):
            return {'dateTime': dt.strftime('%Y-%m-%dT%H:%M:%S'),
                    'timeZone': str(dt.tzinfo)}
        
        return ({
                'summary': str(ical_e['SUMMARY']),
                'start': parse_datetime(ical_e['DTSTART'].dt),
                'end': parse_datetime(ical_e['DTEND'].dt),
                'description': str(ical_e.get('DESCRIPTION', '')),
                'location': str(ical_e.get('LOCATION', '')),
        } for ical_e in self.get_ical_events(dates))


class Service():
    def __init__(self, scopes, config):
        creds = None
        if os.path.exists(config['creds_cache']):
            creds = Credentials.from_authorized_user_file(
                config['creds_cache'], scopes)

        if creds is None or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                config['creds_file'], scopes)
            creds = flow.run_local_server(port=0)
            with open(config['creds_cache'], 'w') as token:
                token.write(creds.to_json())

        if creds is None or not creds.valid:
            raise RuntimeError(
                f'Failed to authenticate using {config["creds_file"]}')

        self._service = build('calendar', 'v3', credentials=creds)
        print('[+] Authenticated')

    def get_events(self, calendar_id, dates=None, max_results=1000):
        def to_google_format(d):
            start, end = d
            
            timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            tz_offset = timezone.utcoffset(datetime.datetime.now())
            sign = '+' if tz_offset.days >= 0 and tz_offset.seconds >= 0 else '-'
            hours = str(tz_offset.seconds // (60 ** 2)).zfill(2)
            minutes = str((tz_offset.seconds // 60) % 60).zfill(2)
            
            format_date = lambda dt: dt.strftime(f'%Y-%m-%dT00:00:00{sign}{hours}:{minutes}')
            return (format_date(start), format_date(end))
        
        if dates is None:
            events_query = self._service.events().list(calendarId=calendar_id, maxResults=max_results)
        else:
            start_time, end_time = to_google_format(dates)
            events_query = self._service.events().list(
                    calendarId=calendar_id, timeMin=start_time, timeMax=end_time, maxResults=max_results)
        
        return events_query.execute().get('items')

    def make_batch_request(self):
        return self._service.new_batch_http_request()

    def make_create_event_request(self, calendar_id, event):
        return self._service.events().insert(calendarId=calendar_id, body=event)

    def make_delete_event_request(self, calendar_id, event_id):
        return self._service.events().delete(calendarId=calendar_id, eventId=event_id)


def parse_config():
    if len(sys.argv) < 2:
        raise RuntimeError(f'Usage: {sys.argv[0]} <config_json> [--next-week]')

    config_path = sys.argv[1]
    with open(config_path, 'rb') as config_stream:
        config = json.load(config_stream)

    return config


date_range = namedtuple('date_range', ('start', 'end'))


def get_week_range():
    today = datetime.date.today()
    # + 1 since our weeks start on Sunday, not Monday :)
    start = today - datetime.timedelta(days=today.weekday() + 1)
    if len(sys.argv) == 3 and sys.argv[2] == '--next-week':
        start += datetime.timedelta(days=7)
    # recurring_ical_events between method is exclusive on end range
    end = start + datetime.timedelta(days=7) 
    return date_range(start, end)


def filter_event(event):
    return {
        'summary': event['summary'],
        'location': event.get('location', None),
        'start': event['start'],
        'end': event['end'],
    }


def main():
    config = parse_config()
    service = Service(SCOPES, config)

    master_ical = ICal.from_url(config['master_ical_url'])
    dates = get_week_range()
    print(f'[+] Working on {dates}')

    print('[+] Retrieving events from master')
    master_events = [(event, filter_event(event)) for event in master_ical.get_luzer_events(dates)]

    print('[+] Deleteing events from shadow calendars')
    for shadow in config['shadow_calendars']:
        batch_request = service.make_batch_request()
        shadow_id = shadow['id']
        
        for event in service.get_events(shadow_id, dates):
            batch_request.add(service.make_delete_event_request(shadow_id, event['id']))
            
        batch_request.execute()

    print('[+] Copying new events to shadow calendars')
    for shadow in config['shadow_calendars']:
        batch_request = service.make_batch_request()
        shadow_id = shadow['id']
        shadow_marking = shadow['marking']
        
        for event, filtered_event in master_events:
            if shadow_marking in event.get('description', ''):
                batch_request.add(service.make_create_event_request(shadow_id, filtered_event))
        batch_request.execute()
            
    print('[+] Done')


if __name__ == '__main__':
    main()
