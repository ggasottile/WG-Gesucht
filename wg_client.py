"""
WG-Gesucht API Client
Based on https://github.com/Zero3141/WgGesuchtAPI
Adapted for the auto-messenger bot.
"""

import requests
import json
import time


class WgGesuchtClient:

    API_URL = 'https://www.wg-gesucht.de/api/{}'
    APP_VERSION = '1.28.0'
    APP_PACKAGE = 'com.wggesucht.android'
    CLIENT_ID = 'wg_mobile_app'
    USER_AGENT = (
        'Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD1A.210817.036; wv) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
        'Chrome/120.0.6099.230 Mobile Safari/537.36'
    )

    def __init__(self):
        self.userId = None
        self.accessToken = None
        self.refreshToken_ = None
        self.phpSession = None
        self.devRefNo = None

    def request(self, method: str, endpoint: str, params=None, payload=None, attempt: int = 0):
        url = self.API_URL.format(endpoint)

        cookies = [
            f'PHPSESSID={self.phpSession}' if self.phpSession else None,
            f'X-Client-Id={self.CLIENT_ID}',
            f'X-Refresh-Token={self.refreshToken_}' if self.refreshToken_ else None,
            f'X-Access-Token={self.accessToken}' if self.accessToken else None,
            f'X-Dev-Ref-No={self.devRefNo}' if self.devRefNo else None,
        ]
        cookie_header = '; '.join(c for c in cookies if c)

        headers = {
            'X-App-Version': self.APP_VERSION,
            'User-Agent': self.USER_AGENT,
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json',
            'X-Client-Id': self.CLIENT_ID,
            'Cookie': cookie_header,
            'X-Requested-With': self.APP_PACKAGE,
        }
        if self.accessToken:
            headers['X-Authorization'] = f'Bearer {self.accessToken}'
        if self.userId:
            headers['X-User-Id'] = self.userId
        if self.devRefNo:
            headers['X-Dev-Ref-No'] = self.devRefNo
        if not self.accessToken:
            headers['Origin'] = 'file://'

        r = requests.request(method=method, url=url, headers=headers, params=params, data=payload, timeout=30)

        if r.status_code in range(200, 300):
            return r
        elif r.status_code == 401 and attempt < 1:
            if self.do_refresh_token():
                return self.request(method, endpoint, params, payload, attempt + 1)
            else:
                print(f'Refresh token request failed: {r.text}')
                return None
        else:
            print(f'Request failed ({r.status_code}): {r.text}')
            return None

    def import_account(self, config: dict):
        self.userId = config['userId']
        self.accessToken = config['accessToken']
        self.refreshToken_ = config['refreshToken']
        self.phpSession = config['phpSession']
        self.devRefNo = config['devRefNo']

    def export_account(self) -> dict:
        return {
            'userId': self.userId,
            'accessToken': self.accessToken,
            'refreshToken': self.refreshToken_,
            'phpSession': self.phpSession,
            'devRefNo': self.devRefNo
        }

    def login(self, username: str, password: str) -> bool:
        payload = {
            'login_email_username': username,
            'login_password': password,
            'client_id': self.CLIENT_ID,
            'display_language': 'de'
        }
        r = self.request('POST', 'sessions', None, json.dumps(payload))
        if r:
            body = r.json()
            self.accessToken = body['detail']['access_token']
            self.refreshToken_ = body['detail']['refresh_token']
            self.userId = body['detail']['user_id']
            self.devRefNo = body['detail']['dev_ref_no']
            self.phpSession = r.cookies.get('PHPSESSID', '')
            return True
        return False

    def do_refresh_token(self) -> bool:
        payload = {
            'grant_type': 'refresh_token',
            'access_token': self.accessToken,
            'refresh_token': self.refreshToken_,
            'client_id': self.CLIENT_ID,
            'dev_ref_no': self.devRefNo,
            'display_language': 'de'
        }
        url = f'sessions/users/{self.userId}'
        r = self.request('POST', url, None, json.dumps(payload))
        if r:
            body = r.json()
            self.accessToken = body['detail']['access_token']
            self.refreshToken_ = body['detail']['refresh_token']
            self.devRefNo = body['detail']['dev_ref_no']
            return True
        return False

    def find_city(self, query: str):
        r = self.request('GET', f'location/cities/names/{query}')
        if r:
            return r.json()['_embedded']['cities']
        return None

    def offers(self, city_id: str, categories: str, max_rent: str, min_size: str, page: str = '1'):
        params = {
            'ad_type': '0',
            'categories': categories,
            'city_id': city_id,
            'noDeact': '1',
            'img': '1',
            'limit': '25',
            'rMax': max_rent,
            'sMin': min_size,
            'rent_types': categories,
            'page': page
        }
        r = self.request('GET', 'asset/offers/', params)
        if r:
            return r.json().get('_embedded', {}).get('offers', [])
        return None

    def offer_detail(self, offer_id: str):
        r = self.request('GET', f'public/offers/{offer_id}')
        if r:
            return r.json()
        return None

    def contact_offer(self, offer_id: str, message: str):
        payload = {
            'user_id': self.userId,
            'ad_type': 0,
            'ad_id': int(offer_id),
            'messages': [
                {
                    'content': message,
                    'message_type': 'text'
                }
            ]
        }
        r = self.request('POST', 'conversations', None, json.dumps(payload))
        if r:
            return r.json().get('messages', [])
        return None
