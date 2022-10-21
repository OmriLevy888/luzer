#!/usr/bin/env python3
import requests

# Read all events from a hardcoded master

# Create events in a hardcoded shadow

# Delete evnets in a hardcoded shadow

# Transfer events from a hardcoded master to multiple hardcoded shadows

# Gather master and shadows from a config file


API_BASE = 'https://www.googleapis.com/calendar/v3'


MASTER_ID = 'f560d2b75e5aba53d1c78d50c413d589149a05be9c5efebec28398e350c26161@group.calendar.google.com'


def get_event_ids(calendar_id):
    requests_fmt = f'{API_BASE}/calendars/{calendar_id}/events'
    print(requests_fmt)
    resp = requests.get(requests_fmt, headers={})
    print(resp)
    print(dir(resp))


def get_event_data(calendar_id, event_id):
    requests_fmt = 'GET /calendars/{calendar_id}/events/{event_id}'


def get_events(calendar_id):
    pass


def create_event(calendar_id, event):
    requests_fmt = 'POST /calendars/{calendar_id}/events'


def remove_event(calendar_id, event_id):
    requests_fmt = 'DELETE /calendars/{calendar_id}/events/{event_id}'


def main():
    get_event_ids(MASTER_ID)


if __name__ == '__main__':
    main()
