import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *
from typing import Dict, Optional, MutableMapping
import requests
import urllib3

# Disable insecure warnings
urllib3.disable_warnings()


def convert_unix_to_date(date):
    """Convert unix timestamp to datetime in iso format.

    Args:
        date: the date in unix to convert.

    Returns:
        converted date.
    """
    return datetime.fromtimestamp(int(date) / 1000).isoformat()


class Client(BaseClient):
    """
    Client to use in the Exabeam integration. Overrides BaseClient
    """
    def __init__(self, base_url: str, username: str, password: str, verify: bool,
                 proxies: Optional[MutableMapping[str, str]], headers):
        super().__init__(base_url=f'{base_url}', verify=verify, proxy=proxies)
        self.username = username
        self.password = password
        self.headers = headers
        self.session = requests.Session()
        self.session.headers = headers
        self._login()

    def __del__(self):
        self._logout()

    def http_request(self, method: str, url_suffix: str = None, full_url: str = None, params: dict = None,
                     data: dict = None, resp_type: str = 'json'):
        """
        Generic request to Exabeam
        """
        full_url = full_url if full_url else f'{self._base_url}{url_suffix}'
        try:
            res = self.session.request(
                method,
                full_url,
                verify=self._verify,
                data=data,
                proxies=self._proxies,
                params=params
            )
            if not res.ok:
                raise ValueError(f'Error in API call to Exabeam {res.status_code}. Reason: {res.text}')

            try:
                if resp_type == 'json':
                    return res.json()
                return res.text
            except Exception:
                raise ValueError(
                    f'Failed to parse http response to JSON format. Original response body: \n{res.text}')

        except requests.exceptions.ConnectTimeout as exception:
            err_msg = 'Connection Timeout Error - potential reasons might be that the Server URL parameter' \
                      ' is incorrect or that the Server is not accessible from your host.'
            raise DemistoException(err_msg, exception)

        except requests.exceptions.SSLError as exception:
            err_msg = 'SSL Certificate Verification Failed - try selecting \'Trust any certificate\' checkbox in' \
                      ' the integration configuration.'
            raise DemistoException(err_msg, exception)

        except requests.exceptions.ProxyError as exception:
            err_msg = 'Proxy Error - if the \'Use system proxy\' checkbox in the integration configuration is' \
                      ' selected, try clearing the checkbox.'
            raise DemistoException(err_msg, exception)

        except requests.exceptions.ConnectionError as exception:
            # Get originating Exception in Exception chain
            error_class = str(exception.__class__)
            err_type = '<' + error_class[error_class.find('\'') + 1: error_class.rfind('\'')] + '>'
            err_msg = f'\nError Type: {err_type}\nError Number: [{exception.errno}]\nMessage: {exception.strerror}\n ' \
                      f'Verify that the server URL parameter ' \
                      f'is correct and that you have access to the server from your host.'
            raise DemistoException(err_msg, exception)

    def _login(self):
        """
        Login using the credentials and store the cookie
        """
        self.http_request('POST', full_url=f'{self._base_url}/api/auth/login', data={
            'username': self.username,
            'password': self.password
        })

    def _logout(self):
        """
        Logout from the session
        """
        self.http_request('GET', self.http_request('GET', f'{self._base_url}/api/auth/logout'))

    def test_module_request(self):
        """
        Performs basic get request to check if the server is reachable.
        """
        self.http_request('GET', '/uba/api/ping', resp_type='text')

    def get_notable_users_request(self, api_unit: str = None, num: str = None, limit: int = None):
        """
        Args:
            api_unit:
            num: num of notable users
            limit: limit of notable users

        Returns:
            notable users
        """
        params = {
            'unit': api_unit,
            'num': num,
            'numberOfResults': limit
        }
        response = self.http_request('GET', '/uba/api/users/notable', params=params)
        return response

    def get_user_info_request(self, username: str):
        """
        Args:
            username: the username

        Returns:
            the user info
        """
        response = self.http_request('GET', f'/uba/api/user/{username}/info')
        return response

    def get_peergroups_request(self):
        """
        Returns:
            peer groups
        """
        response = self.http_request('GET', '/uba/api/peerGroup')
        return response

    def get_user_labels_request(self):
        """
        Returns:
            user labels
        """
        response = self.http_request('GET', '/uba/api/userLabel')
        return response

    def user_sequence_request(self, username: str = None, parse_start_time=None, parse_end_time=None):
        """
        Args:
            username:
            parse_start_time: start time
            parse_end_time: end time

        Returns:
            user sequence relevant to the time period
        """
        params = {
            'username': username,
            'startTime': parse_start_time,
            'endTime': parse_end_time
        }
        response = self.http_request('GET', f'/uba/api/user/{username}/sequences', params=params)
        return response

    def get_watchlist_request(self):
        """
        Returns:
            a watchlist
        """
        response = self.http_request('GET', '/uba/api/watchlist')
        return response

    def create_watchlist_request(self, title=None, category=None, description=None, items=None):
        """
        Args:
            title: watchlist title
            category: watchlist category
            description: watchlist description
            items: watchlist items

        Returns:
            a watchlist
        """
        params = {
            'title': title,
            'category': category,
            'description': description,
            'items': items
        }
        response = self.http_request('POST', '/uba/api/watchlist', params=params)
        return response.json()

    def watchlist_add_user_request(self, user_id: str = None, watchlist_id: str = None):
        """
        Args:
            user_id: user id
            watchlist_id: watchlist id

        Returns:
            all updated watchlist
        """
        params = {
            'itemId': user_id,
            'watchListId': watchlist_id
        }
        response = self.http_request('PUT', 'f/uba/api/watchlist/user/{user_id}/add', params=params)
        return response.json()

    def delete_watchlist_request(self, watchlist_id: str = None):
        """
        Args:
            watchlist_id: watchlist id

        """
        self.http_request('DELETE', f'watchlist/{watchlist_id}')

    def get_asset_data_request(self, asset_id: str = None):
        """

        Args:
            asset_id: asser ud

        Returns:
            asset data
        """
        response = self.http_request('GET', f'asset/{asset_id}/data')
        return response.json()


def test_module(client: Client, *_):
    """test function

    Args:
        client:
        *_:

    Returns:
        ok if successful
    """
    client.test_module_request()
    demisto.results('ok')
    return '', None, None


def contents_append_notable_user_info(contents, user, user_, user_info):
    """Appends a dictionary of data to the base list

    Args:
        contents: base list
        user: user object
        user_: user object
        user_info: user info object

    Returns:
        A contents list with the relevant notable user data
    """
    contents.append({
        'UserName': user_.get('username'),
        'RiskScore': round(user_info.get('riskScore')) if 'riskScore' in user_info else None,
        'FirstSeen': convert_unix_to_date(user_.get('firstSeen')),
        'LastSeen': convert_unix_to_date(user_.get('lastSeen')),
        'LastActivity': user_.get('lastActivityType'),
        'Labels': user_.get('labels'),
        'UserFullName': user.get('userFullName'),
        'Location': user_.get('info')['location'],
        'NotableSessionIds': user.get('notableSessionIds'),
        'NotableUser': True,
        'HighestRiskSession': user.get('highestRiskSession'),
        'EmployeeType': user_info.get('employeeType'),
        'Department': user_info.get('department'),
        'Title': user_info.get('title')
    })
    return contents


def get_notable_users(client: Client, args: Dict):
    """ Get notable users in a period of time

    Args:
        client: Client
        args: Dict

    """
    limit: int = args.get('limit', 10)
    time_period: str = args.get('time_period', '')
    time_ = time_period.split(' ')
    if not len(time_) == 2:
        raise Exception('Got invalid time period. Enter the time period number and unit.')
    num: str = time_[0]
    unit: str = time_[1]
    api_unit = unit[0]
    if api_unit == 'm':
        api_unit = api_unit.upper()

    if api_unit not in {'d', 'y', 'M', 'h'}:
        raise Exception('The time unit is incorrect - can be hours, days, months, years.')

    contents = []
    headers = ['UserFullName', 'UserName', 'Title', 'Department', 'RiskScore', 'Labels', 'NotableSessionIds',
               'EmployeeType', 'FirstSeen', 'LastSeen', 'LastActivity', 'Location']
    users = client.get_notable_users_request(api_unit, num, limit).get('users', [])
    if not users:
        return 'No users were found in this period of time.', {}, {}

    for user in users:
        user_ = user.get('user', {})
        user_info = user_.get('info', {})
        contents = contents_append_notable_user_info(contents, user, user_, user_info)

    entry_context = {'Exabeam.User(val.UserName && val.UserName === obj.UserName)': contents}
    human_readable = tableToMarkdown('Exabeam Notable Users', contents, headers=headers, removeNull=True)

    return human_readable, entry_context, users


def contents_user_info(user, user_info):
    """create a content obj for the user

    Args:
        user: user object
        user_info: user info object

    Returns:
        A contents dict with the relevant user data
    """
    contents = {
        'Username': user.get('username'),
        'RiskScore': round(user_info.get('riskScore')) if 'riskScore' in user_info else None,
        'AverageRiskScore': user_info.get('averageRiskScore'),
        'LastSessionID': user_info.get('lastSessionId'),
        'FirstSeen': convert_unix_to_date(user_info.get('firstSeen')),
        'LastSeen': convert_unix_to_date(user_info.get('lastSeen')),
        'LastActivityType': user_info.get('lastActivityType'),
        'Label': user_info.get('labels'),
        'AccountNames': user.get('accountNames'),
        'PeerGroupFieldName': user.get('peerGroupFieldName'),
        'PeerGroupFieldValue': user.get('peerGroupFieldValue'),
        'PeerGroupDisplayName': user.get('peerGroupDisplayName'),
        'PeerGroupType': user.get('peerGroupType')
    }
    return contents


def get_user_info(client: Client, args: Dict):
    """Returns User info data for the given username
    Args:
        client: Client
        args: Dict

    """
    username: str = args.get('username', '')
    headers = ['Username', 'RiskScore', 'AverageRiskScore', 'LastSessionID', 'Labels', 'FirstSeen',
               'LastSeen', 'LastActivityType', 'AccountNames', 'PeerGroupFieldName', 'PeerGroupFieldValue',
               'PeerGroupDisplayName', 'PeerGroupType']
    user = client.get_user_info_request(username)
    user_info = user.get('userInfo', {})
    if not user_info:
        raise Exception('User has no info. Please check that the username and not the userFullName    was inserted.')
    contents = contents_user_info(user, user_info)
    context = {'Exabeam.User(val.UserName && val.UserName === obj.UserName)': contents}

    if not user_info.get('firstSeen'):
        return f'The user {username} was not found', {}, {}

    human_readable = tableToMarkdown(f'User {username} information', contents, headers, removeNull=True)
    return human_readable, context, user


def get_user_sessions(client: Client, args: Dict):
    """Returns sessions for the given username and time range

    Args:
        client: Client
        args: Dict

    """
    username = args.get('username')
    start_time = args.get('start_time', datetime.now() - timedelta(days=30))
    end_time = args.get('end_time', datetime.now())
    parse_start_time = date_to_timestamp(start_time)
    parse_end_time = date_to_timestamp(end_time)
    contents = []
    headers = ['SessionID', 'RiskScore', 'InitialRiskScore', 'StartTime', 'EndTime', 'LoginHost', 'Label']

    user = client.user_sequence_request(username, parse_start_time, parse_end_time)
    session = user.get('sessions')
    if not session:
        return f'The user {username} was not found.', {}, {}

    for session_ in session:
        contents.append({
            'SessionID': session_.get('sessionId'),
            'StartTime': convert_unix_to_date(session_.get('startTime')),
            'EndTime': convert_unix_to_date(session_.get('endTime')),
            'InitialRiskScore': session_.get('initialRiskScore'),
            'RiskScore': round(session_.get('riskScore')),
            'LoginHost': session_.get('loginHost'),
            'Label': session_.get('label')
        })

    entry_context = {
        'Exabeam.User(val.SessionID && val.SessionID === obj.SessionID)': {
            'Username': username,
            'Session': contents
        }
    }
    human_readable = tableToMarkdown(f'User {username} sessions information', contents, headers, removeNull=True)

    return human_readable, entry_context, user


def get_peer_groups(client: Client, *_):
    """Returns all peer groups

    Args:
        client: Client

    """
    groups = client.get_peergroups_request()
    contents = []
    for group in groups:
        contents.append({'Name': group})

    entry_context = {'Exabeam.PeerGroup(val.Name && val.Name === obj.Name)': contents}
    human_readable = tableToMarkdown('Exabeam Peer Groups', contents)

    return human_readable, entry_context, groups


def get_user_labels(client: Client, *_):
    """ Returns all user Labels

    Args:
        client: Client

    """
    labels = client.get_user_labels_request()
    contents = []
    for label in labels:
        contents.append({'Label': label})

    entry_context = {'Exabeam.UserLabel(val.Label && val.Label === obj.Label)': contents}
    human_readable = tableToMarkdown('Exabeam User Labels:', contents)

    return human_readable, entry_context, labels


def get_watchlist(client: Client, *_):
    """  Returns all watchlist ids and titles.

    Args:
        client: Client

    """

    watchlist = client.get_watchlist_request()
    contents = []
    for list_ in watchlist:
        contents.append({
            'WatchlistID': list_.get('watchlistId'),
            'Title': list_.get('title'),
            'Category': list_.get('category')
        })

    entry_context = {'Exabeam.Watchlist(val.WatchlistID && val.WatchlistID === obj.WatchlistID)': contents}
    human_readable = tableToMarkdown('Exabeam Watchlists:', contents, headers=['WatchlistID', 'Title', 'Category'])

    return human_readable, entry_context, watchlist


def create_watchlist(client: Client, args: Dict):
    """Create a new watchlist

    Args:
        client: Client
        args: Dict

    """
    title = args.get('title')
    category = args.get('category')
    description = args.get('description')
    items = argToList(args.get('items'))

    watchlist = client.create_watchlist_request(title, category, description, items)
    if not watchlist:
        raise Exception(f'The watchlist was not created.')

    contents = {
        'WatchlistID': watchlist.get('watchlistId'),
        'Title': watchlist.get('title'),
        'Category': watchlist.get('category')
    }
    entry_context = {'Exabeam.Watchlist(val.WatchlistID && val.WatchlistID === obj.WatchlistID)': contents}
    human_readable = tableToMarkdown('New watchlist has been created', t=contents,
                                     headers=['WatchlistID', 'Title', 'Category'])
    return human_readable, entry_context, watchlist


def watchlist_add_user(client, args: Dict):
    """Add user to a watchlist

    Args:
        client: Client
        args: Dict

    """
    user_id = args.get('user_id')
    watchlist_id = args.get('watchlist_id')

    response = client.watchlist_add_user_request(user_id, watchlist_id)
    if not response:
        raise Exception(f'The user {user_id} was not added to the watchlist {watchlist_id}.')

    contents = {
        'UserID': response.get('item'),
        'WatchlistID': response.get('watchlistId')
    }
    entry_context = {'Exabeam.Watchlist(val.WatchlistID && val.WatchlistID === obj.WatchlistID)': contents}
    human_readable = tableToMarkdown('The user was added successfully to the watchlist.', contents)

    return human_readable, entry_context, response


def delete_watchlist(client: Client, args: Dict):
    """Delete a watchlist

    Args:
        client: Client
        args: Dict

    """

    watchlist_id = args.get('watchlist_id')
    client.delete_watchlist_request(watchlist_id)

    return f'The watchlist {watchlist_id} was deleted successfully.', {}, {}


def contents_asset_data(asset_data):
    """create a content obj for the asset

    Args:
        asset_data: asset data
    Returns:
        A contents dict with the relevant asset data
    """
    contents = {
        'HostName': asset_data.get('hostName'),
        'IPAddress': asset_data.get('ipAddress'),
        'AssetType': asset_data.get('assetType'),
        'FirstSeen': convert_unix_to_date(asset_data.get('firstSeen')),
        'LastSeen': convert_unix_to_date(asset_data.get('lastSeen')),
        'Labels': asset_data.get('labels')
    }
    return contents


def get_asset_data(client: Client, args: Dict):
    """  Return asset data for given asset ID (hostname or IP address)

    Args:
        client: Client
        args: Dict

    """
    asset_id = args.get('asset_id')
    asset_data = client.get_asset_data_request(asset_id)

    if not asset_data or not 'asset' in asset_data:
        raise Exception(f'The asset {asset_id} have no data. Please verify that the asset id is valid.')

    asset_data = asset_data.get('asset', None)
    contents = contents_asset_data(asset_data)
    entry_context = {'Exabeam.Asset(val.IPAddress && val.IPAddress === obj.IPAddress)': contents}
    human_readable = tableToMarkdown('Exabeam Asset Data:', contents, removeNull=True)

    return human_readable, entry_context, asset_data


def main():
    """
    PARSE AND VALIDATE INTEGRATION PARAMS
    """
    username = demisto.params().get('credentials').get('identifier')
    password = demisto.params().get('credentials').get('password')
    base_url = demisto.params().get('url')
    verify_certificate = not demisto.params().get('insecure', False)
    headers = {'Accept': 'application/json'}
    proxies = handle_proxy()

    client = Client(base_url.rstrip('/'), verify=verify_certificate, username=username, password=password, proxies=proxies,
                    headers=headers)
    commands = {
        'test-module': test_module,
        'get-notable-users': get_notable_users,
        'exabeam-get-notable-users': get_notable_users,
        'get-peer-groups': get_peer_groups,
        'exabeam-get-peer-groups': get_peer_groups,
        'get-user-info': get_user_info,
        'exabeam-get-user-info': get_user_info,
        'get-user-labels': get_user_labels,
        'exabeam-get-user-labels': get_user_labels,
        'get-user-sessions': get_user_sessions,
        'exabeam-get-user-sessions': get_user_sessions,
        'get-watchlists': get_watchlist,
        'exabeam-get-watchlists': get_watchlist,
        'exabeam-create-watchlist': create_watchlist,
        'exabeam-watchlist-add-user': watchlist_add_user,
        'exabeam-delete-watchlist': delete_watchlist,
        'exabeam-get-asset-data': get_asset_data
    }

    try:
        command = demisto.command()
        LOG(f'Command being called is {command}')
        if command in commands:
            return_outputs(*commands[command](client, demisto.args()))  # type: ignore
        else:
            raise NotImplementedError(f'Command "{command}" is not implemented.')

    except Exception as err:
        return_error(str(err))


if __name__ in ['__main__', 'builtin', 'builtins']:
    main()