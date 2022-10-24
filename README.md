# Luzer
-------

Luzer is a short script to transfer events from a master calendar to shadow calendars. It supprots any amount of shadow calenars.

Luzer does not copy any description points from the master calendar to the shadow calendars (TODO: consider adding this as a switch).

Luzer only copies the current week from the master calendar (TODO: consider making this adjustable).

#TODO:

- [ ] Fetch
  - When using the google calendar API to fetch data from the calendar, some events are mising(???) and there are also some events that return twice.
  - Solve this by parsing the .ics file (calendar file, can be exported from google calendar GUI under the settings, might be worth it to get it automatically but not a big problem if this is provided from the command line). Need to make sure that recurring evets are parsd correctly. The point is to get the list of events from the calendar, most importantly, to get the summary, start and end time and location. Color would also be nice to have. Make sure you take time zones into ccount!
- [ ] Upload
  - To upload the events to the shadow calendars, the current method is to first delete everything in the time range which we want to update and then to create the events. This also requires us to fetch the calendars in their current form... Currnetly, each request (the fetch of all the events, once per deletion and once per event creation) is a separate request. This is slow af.
  - Google provides a batch request API. I tried it and couldn't make it work. If you can, I wil literally donate my kidney to you.
  - Another solution is to ues the aiogoogle python package. I haven't looked to much into it but it should be able to execute google API requests asynchronously, which would be great.
