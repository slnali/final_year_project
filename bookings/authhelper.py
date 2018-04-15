
import datetime

import requests
from django.utils import timezone

from meeting_scheduler.secret_settings import CLIENT_SECRET

URI_CALLBACK = '/accounts/microsoft/login/callback/'

client_id = 'c82fc9db-5118-4581-91ed-b3c586820b72'

#  OAuth authority URL enables OAurh2 credential flow
authority = 'https://login.microsoftonline.com'
authorize_url = '{0}{1}'.format(authority, '/common/oauth2/v2.0/authorize?{0}')

#  token  endpoint
token_url = '{0}{1}'.format(authority, '/common/oauth2/v2.0/token')

scopes = ['openid',
          'offline_access',
          'User.Read',
          'Mail.Read',
          'Calendars.Read']

def get_new_access_token_from_refresh_token(refresh_token, redirect_uri):
    '''
    Query graph endpoint to refresh token
    :param refresh_token: 
    :param redirect_uri: usually a callback url
    :return: dict containing access token
    '''
    # Build the post form for the token request
    payload = {'grant_type': 'refresh_token',
                 'refresh_token': refresh_token,
                 'redirect_uri': redirect_uri,
                 'scope': ' '.join(str(i) for i in scopes),
                 'client_id': client_id,
                 'client_secret': CLIENT_SECRET
                 }

    r = requests.post(token_url, data=payload)

    try:
        return r.json()
    except:
        return 'Error obtaining token: {0} - {1}'.format(r.status_code, r.text)


def set_new_token(request,token_obj):
    '''
    Obtain new access token through refresh token
    :param token_obj:
    :return: Void
    '''
    if token_obj.expires_at < timezone.now():
        refresh_token = token_obj.token_secret
        response = get_new_access_token_from_refresh_token(refresh_token, request.build_absolute_uri(URI_CALLBACK))
        token_obj.token_secret = response['refresh_token']
        token_obj.token = response['access_token']
        token_obj.expires_at = timezone.now() + datetime.timedelta(hours=1)
        token_obj.save()