import json
import uuid

import requests

graph_endpoint = 'https://graph.microsoft.com/v1.0{0}'


def make_api_call(method, url, token, user_email, payload=None, parameters=None):
    '''
    Make HTTP requests to REST API endpoint
    :param method: HTTP method e.g GET,POST
    :param url: endpoint of server to send request to
    :param token: authorization & authentication token
    :param user_email:
    :param payload: submit data to endpoint
    through a dictionary that is parsed to JSON
    :param parameters: query parameters for retrieving
    specfic data
    :return:
    '''
    request_id = str(uuid.uuid4())
    headers = {'User-Agent': 'meeting_scheduler/1.0',
               'Authorization': 'Bearer {0}'.format(token),
               'Accept': 'application/json',
               'X-AnchorMailbox': user_email,
               'Prefer': 'outlook.timezone="Europe/London"',
               # instrumentation
               'client-request-id': request_id,
               'return-client-request-id': 'true'
               }

    response = None
    if method.upper() == 'GET':
        response = requests.get(url, headers=headers, params=parameters)
    elif method.upper() == 'DELETE':
        response = requests.delete(url, headers=headers, params=parameters)
    elif method.upper() == 'PATCH':
        headers.update({'Content-Type': 'application/json'})
        response = requests.patch(url, headers=headers, data=json.dumps(payload), params=parameters)
    elif method.upper() == 'POST':
        headers.update({'Content-Type': 'application/json'})
        response = requests.post(url, headers=headers, data=json.dumps(payload), params=parameters)
    return response


def get_outlook_events(access_token, user_email):
    '''
    Get outlook events
    # Use OData query parameters to control the results
    Params order
    #  - first 10 results returned
    #  - get Subject, Start, and End fields
    #  - sort results by start field in ascending datetime order
    :param access_token:
    :param user_email:
    :return: dict containing events
    '''
    events_endpoint = graph_endpoint.format('/me/events')
    query_params = {'$top': '10',
                    '$select': 'subject,start,end',
                    '$orderby': 'start/dateTime ASC'}

    r = make_api_call('GET', events_endpoint, access_token, user_email, parameters=query_params)
    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def get_events_between_dates(access_token, user_email, start_date, end_date):
    '''
    Get outlook events between a start and end date
    :param access_token:
    :param user_email:
    :param start_date: iso format start date
    :param end_date: iso format end date
    :return: dictionary containing value key which maps to list of dicts for each event
    '''
    events_endpoint = graph_endpoint.format('/me/calendarview')
    query_params = {'startdatetime': start_date,
                    'enddatetime': end_date}
    r = make_api_call('GET', events_endpoint, access_token, user_email, parameters=query_params)
    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def update_booking(access_token, user_email, event, body_content):
    '''
    Update existing outlook event time
    :param access_token:
    :param user_email:
    :param event: dict containing subject, start and end time
    :param body_content: HTML content for update email auto sent by user
    :return: dict response containing saved event data or string if errored
    '''
    events_endpoint = graph_endpoint.format('/me/events/{}'.format(event['outlook_id']))
    payload = {
        "subject": event['subject'],
        "body": {
            "contentType": "HTML",
            "content": body_content
        },
        "start": {
            "dateTime": event['start_time'].astimezone().isoformat(),
            "timeZone": "Europe/London"
        },
        "end": {
            "dateTime": event['end_time'].astimezone().isoformat(),
            "timeZone": "Europe/London"
        },
    }
    r = make_api_call('PATCH', events_endpoint, access_token, user_email, payload=payload)
    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return "{}: {} Request: {}".format(r.status_code, r.text, payload)


def cancel_booking(access_token, user_email, event_id):
    '''
    Cancel existing event
    :param access_token:
    :param user_email:
    :param event_id: outlook id of users event
    :return: True if event was successfully cancelled (204) else False
    '''
    events_endpoint = graph_endpoint.format('/me/events/{}'.format(event_id))
    r = make_api_call('DELETE', events_endpoint, access_token, user_email)
    # check that the request has been processed but no content has been responded (204)
    return True if r.status_code == requests.codes.no_content else False


def book_event(access_token, user_email, event, body_content):
    '''
    Books a meeting/event for a specified start and end time
    email is auto sent through outlook client to notify
    :param access_token:
    :param user_email:
    :param event: event dict containing event info
    :param body_content: HTML content to be sent in email auto sent to booker by user
    :return: dict with booking details including created event id
    '''
    events_endpoint = graph_endpoint.format('/me/events')

    payload = {
        "subject": event['subject'],
        "body": {
            "contentType": "HTML",
            "content": body_content
        },
        "start": {
            "dateTime": event['start_time'].astimezone().isoformat(),
            "timeZone": "Europe/London"
        },
        "end": {
            "dateTime": event['end_time'].astimezone().isoformat(),
            "timeZone": "Europe/London"
        },
        "attendees": [
            {
                "emailAddress": {
                    "address": event['email'],
                    "name": event['first_name'],
                },
                "type": "optional"
            }
        ]
    }

    r = make_api_call('POST', events_endpoint, access_token, user_email, payload=payload)
    # check if resource has been created (201)
    if r.status_code == requests.codes.created:
        return r.json()
    else:
        return "{}: {} Request: {}".format(r.status_code, r.text, payload)
