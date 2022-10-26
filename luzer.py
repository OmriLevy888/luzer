#!/usr/bin/env python3
import os
import datetime
from collections import namedtuple
import json
import sys
import ics
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ['https://www.googleapis.com/auth/calendar']


date_range = namedtuple('date_range', ('start', 'end'))


def get_week_range():
    today = datetime.date.today()
    # + 1 since our weeks start on Sunday, not Monday :)
    start = today - datetime.timedelta(days=today.weekday() + 1)
    if len(sys.argv) == 3 and sys.argv[2] == '--next-week':
        start += datetime.timedelta(days=7)
    end = start + datetime.timedelta(days=6)
    return date_range(start, end)


def date_range_to_utc_time(dates):
    # TODO: make timezone change automatically!!!
    start_time = dates.start.isoformat() + 'T00:00:00.000000+03:00'
    end_time = dates.end.isoformat() + 'T23:59:59.999999+03:00'
    return start_time, end_time


class ICS():
    def __init__(self, config):
        # Perfer remote ics over locl
        if config.get('master_ics_url', None) is None:
            with open(config['master_ics_path'], 'r') as ics_f:
                print('[!] Using local ICS file')
                self._ics = ics.Calendar(ics_f.read())
        else:
            print('[+] Using remote ICS file')
            self._ics = ics.Calendar(
                requests.get(config['master_ics_url']).text)

    def write(self, out_ics_path: str) -> None:
        raise NotImplementedError()

    def get_ics_events(self, dates: date_range = None):
        if dates:
            # Yeah, fuckit
            return filter(lambda e: e.begin.datetime.date() >= dates.start and e.end.datetime.date() <= dates.end, self._ics.events)
        return self._ics.timeline  # Generator of events

    def get_luzer_events(self, dates: date_range = None):
        # Normalize ICS events
        return map(lambda ics_e: {'summary': ics_e.name, 'start': {'date': ics_e.begin.strftime('%c')}, 'end': {'date': ics_e.end.strftime('%c')},
                                  'description': ics_e.description or '',
                                  'location': ics_e.location}, self.get_ics_events(dates))


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

    def get_events(self, calendar_id, dates=None):
        if dates is None:
            events_query = self._service.events().list(calendarId=calendar_id)
        else:
            start_time, end_time = date_range_to_utc_time(dates)
            events_query = self._service.events().list(
                calendarId=calendar_id, timeMin=start_time, timeMax=end_time)

        return events_query.execute().get('items')

    def create_event(self, calendar_id, event):
        self._service.events().insert(calendarId=calendar_id, body=event).execute()

    def delete_event(self, calendar_id, event_id):
        self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def delete_calendar_events_range(service, calendar_id, dates):
    for event in service.get_events(calendar_id, dates):
        service.delete_event(calendar_id, event['id'])


def copy_event(event):
    # return copy.deepcopy(event) ?
    copy = dict()
    copy['summary'] = event['summary']
    copy['start'] = event['start']
    copy['end'] = event['end']
    if event.get('location', None) is not None:
        copy['location'] = event['location']

    return copy


def parse_config():
    if len(sys.argv) < 2:
        raise RuntimeError(f'Usage: {sys.argv[0]} <config_json> [--next-week]')

    config_path = sys.argv[1]
    with open(config_path, 'rb') as config_stream:
        config = json.load(config_stream)

    return config


def main():
    config = parse_config()

    service = Service(SCOPES, config)
    master_ics = ICS(config)

    this_week = get_week_range()
    print(f'[+] Working on week {this_week}')

    print('[+] Deleting events from shadow calendars')
    for shadow in config['shadow_calendars']:
        delete_calendar_events_range(service, shadow['id'], this_week)

    print('[+] Retrieving events from master')
    # master_events = service.get_events(config['master_id'], this_week)
    master_events = list(master_ics.get_luzer_events(this_week))
    # Without this log we can do it lazy.
    print(f'[+] Got {len(master_events)} events in the current week')

    shadow_meta = namedtuple('shadow_meta', ('name', 'id'))
    markings_to_shadows = {shadow['marking']: shadow_meta(
        shadow['name'], shadow['id']) for shadow in config['shadow_calendars']}

    for event in master_events:
        if event.get('summary', None) is None:
            print(f'[-] Event {event} does not contain summery')

        for marking, shadow in markings_to_shadows.items():
            if marking in event.get('description', ''):
                print(f'[+] Copying {event["summary"]} to {shadow.name}')
                service.create_event(shadow.id, copy_event(event))


if __name__ == '__main__':
    main()
