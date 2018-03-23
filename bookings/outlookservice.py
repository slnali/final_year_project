import requests
import uuid
import json

'''implement all of our Outlook API functions in this file'''

# This is the resource we would like to access after authentication succeeds
graph_endpoint = 'https://graph.microsoft.com/v1.0{0}'


# Generic API Sending
def make_api_call(method, url, token, user_email, payload=None, parameters=None):
    '''generic method for sending API requests
     This function uses the requests library to send API requests.
     It sets a standard set of headers on each requests, including client instrumentation.

    It also uses the email address we retrieved from the ID token
    to set the X-AnchorMailbox header. By setting this header,
    we enable the API endpoint to route API calls to the correct
     backend mailbox server more efficiently. This is why we want
     to get the user's email address.'''
    # Send these headers with all API calls
    headers = {'User-Agent': 'meeting_scheduler/1.0',
               'Authorization': 'Bearer {0}'.format(token),
               'Accept': 'application/json',
               'X-AnchorMailbox': user_email,
               'Prefer': 'outlook.timezone="Europe/London"'}

    # Use these headers to instrument calls. Makes it easier
    # to correlate requests and responses in case of problems
    # and is a recommended best practice.
    request_id = str(uuid.uuid4())
    instrumentation = {'client-request-id': request_id,
                       'return-client-request-id': 'true'}

    headers.update(instrumentation)

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


def get_me(access_token):
    get_me_url = graph_endpoint.format('/me')

    # Use OData query parameters to control the results
    #  - Only return the displayName and mail fields
    query_parameters = {'$select': 'displayName,mail'}

    r = make_api_call('GET', get_me_url, access_token, "", parameters=query_parameters)

    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def get_my_messages(access_token, user_email):
    '''
    function to implement a request to retrieve messages from the inbox
    :param access_token:
    :param user_email:
    :return:
    '''
    get_messages_url = graph_endpoint.format('/me/mailfolders/inbox/messages')

    # Use OData query parameters to control the results
    #  - Only first 10 results returned
    #  - Only return the ReceivedDateTime, Subject, and From fields
    #  - Sort the results by the ReceivedDateTime field in descending order
    query_parameters = {'$top': '10',
                        '$select': 'receivedDateTime,subject,from',
                        '$orderby': 'receivedDateTime DESC'}

    r = make_api_call('GET', get_messages_url, access_token, user_email, parameters=query_parameters)

    if requests.codes.ok == r.status_code:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def get_my_events(access_token, user_email):
    get_events_url = graph_endpoint.format('/me/events')

    # Use OData query parameters to control the results
    #  - Only first 10 results returned
    #  - Only return the Subject, Start, and End fields
    #  - Sort the results by the Start field in ascending order
    query_parameters = {'$top': '10',
                        '$select': 'subject,start,end',
                        '$orderby': 'start/dateTime ASC'}

    r = make_api_call('GET', get_events_url, access_token, user_email, parameters=query_parameters)

    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def get_events_between_dates(access_token, user_email, start_date, end_date):
    '''

    :param access_token:
    :param user_email:
    :param start_date: iso format start date
    :param end_date: iso format end date
    :return:
    '''
    get_events_url = graph_endpoint.format('/me/calendarview')

    query_parameters = {'startdatetime': start_date,
                        'enddatetime': end_date}

    r = make_api_call('GET', get_events_url, access_token, user_email, parameters=query_parameters)

    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def update_booking(access_token,user_email,event,body_content):
    event_endpoint = graph_endpoint.format('/me/events/{}'.format(event['outlook_id']))
    payload = {
        "subject": event['subject'],
        "body": {
            "contentType": "HTML",
            "content": body_content
        },
        "start": {
            "dateTime": event['start_time'].isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": event['end_time'].isoformat(),
            "timeZone": "UTC"
        },
    }
    r = make_api_call('PATCH', event_endpoint, access_token, user_email, payload=payload)
    if r.status_code == 200:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)


def cancel_booking(access_token, user_email, event_id):
    event_endpoint = graph_endpoint.format('/me/events/{}'.format(event_id))
    r = make_api_call('DELETE', event_endpoint, access_token, user_email)
    if r.status_code == 204:
        return True
    else:
        return False



def book_event(access_token, user_email, event, body_content):
    event_endpoint = graph_endpoint.format('/me/events')

    payload = {
        "subject": event['subject'],
        "body": {
            "contentType": "HTML",
            "content": body_content
        },
        "start": {
            "dateTime": event['start_time'].isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": event['end_time'].isoformat(),
            "timeZone": "UTC"
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

    r = make_api_call('POST', event_endpoint, access_token, user_email, payload=payload)

    if r.status_code == 201:
        return r.json()
    else:
        return "{0}: {1}".format(r.status_code, r.text)
