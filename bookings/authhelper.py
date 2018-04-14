from urllib.parse import quote, urlencode
import time
import requests
import datetime
from django.utils import timezone
from meeting_scheduler.secret_settings import CLIENT_SECRET

REDIRECT_URL = 'http://127.0.0.1:8000/accounts/microsoft/login/callback/' #get server host

# Client ID and secret
client_id = 'c82fc9db-5118-4581-91ed-b3c586820b72'

# Constant strings for OAuth2 flow
# The OAuth authority
authority = 'https://login.microsoftonline.com'

# The authorize URL that initiates the OAuth2 client credential flow for admin consent
authorize_url = '{0}{1}'.format(authority, '/common/oauth2/v2.0/authorize?{0}')

# The token issuing endpoint
token_url = '{0}{1}'.format(authority, '/common/oauth2/v2.0/token')

# The scopes required by the app
# Access tokens returned from Azure are valid for an hour.
# If you use the token after it has expired, the API calls will return 401 errors.
# You could ask the user to sign in again, but the better option is to refresh
# the token silently. In order to do that, the app must request the offline_access
scopes = ['openid',
          'offline_access',
          'User.Read',
          'Mail.Read',
          'Calendars.Read']


def get_signin_url(redirect_uri):
    # Build the query parameters for the signin url
    params = {'client_id': client_id,
              'redirect_uri': redirect_uri,
              'response_type': 'code',
              'scope': ' '.join(str(i) for i in scopes)
              }

    signin_url = authorize_url.format(urlencode(params))

    return signin_url


def get_token_from_code(auth_code, redirect_uri):
    # Build the post form for the token request
    post_data = {'grant_type': 'authorization_code',
                 'code': auth_code,
                 'redirect_uri': redirect_uri,
                 'scope': ' '.join(str(i) for i in scopes),
                 'client_id': client_id,
                 'client_secret': CLIENT_SECRET
                 }

    r = requests.post(token_url, data=post_data)

    try:
        return r.json()
    except:
        return 'Error retrieving token: {0} - {1}'.format(r.status_code, r.text)


def get_token_from_refresh_token(refresh_token, redirect_uri):
    '''
    Query graph endpoint to refresh token
    :param refresh_token: 
    :param redirect_uri: usually a callback url
    :return: dict containing access token
    '''
    # Build the post form for the token request
    post_data = {'grant_type': 'refresh_token',
                 'refresh_token': refresh_token,
                 'redirect_uri': redirect_uri,
                 'scope': ' '.join(str(i) for i in scopes),
                 'client_id': client_id,
                 'client_secret': CLIENT_SECRET
                 }

    r = requests.post(token_url, data=post_data)

    try:
        return r.json()
    except:
        return 'Error retrieving token: {0} - {1}'.format(r.status_code, r.text)





def set_new_token(token_obj):
    '''
    Refresh access token through refresh token
    :param token_obj:
    :return: Void
    '''
    refresh_token = token_obj.token_secret
    response = get_token_from_refresh_token(refresh_token, REDIRECT_URL)  # hardcoded...
    # set newly obtained tokens for token object and save
    token_obj.token_secret = response['refresh_token']
    token_obj.token = response['access_token']
    token_obj.expires_at = timezone.now() + datetime.timedelta(hours=1)
    token_obj.save()