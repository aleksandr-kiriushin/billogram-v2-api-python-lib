# encoding=utf-8
#
# Based on billogram_api created by Billogram AB
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Library for asynchronous accessing the Billogram v2 HTTP API"""

import base64
import copy
import json
import os

import aiohttp

from billogram_api import exceptions as ex

API_URL_BASE = 'https://billogram.com/api/v2'
USER_AGENT = 'Billogram API Async Python Library/1.00'


class BillogramAPI:
    """Pseudo-connection to the Billogram v2 API

    Objects of this class provide a call interface to the Billogram
    v2 HTTP API.
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self, auth_user, auth_key, user_agent=None, api_base=None):
        """Create a Billogram API connection object

        Pass the API authentication in the auth_user and auth_key parameters.
        API accounts can only be created from the Billogram web interface.
        """
        self._auth = aiohttp.BasicAuth(auth_user, auth_key)
        self._items = None
        self._customers = None
        self._billogram = None
        self._settings = None
        self._logotype = None
        self._reports = None
        self._user_agent = user_agent or USER_AGENT
        self._api_base = api_base or API_URL_BASE
        self._session = aiohttp.ClientSession(auth=self._auth)

    async def close(self):
        """Close HTTP session"""
        await self._session.close()

    async def __aenter__(self):
        await self._session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def items(self):
        """Provide access to the items database"""
        if self._items is None:
            self._items = SimpleClass(self, 'item', 'item_no')
        return self._items

    @property
    def customers(self):
        """Provide access to the customer database"""
        if self._customers is None:
            self._customers = SimpleClass(self, 'customer', 'customer_no')
        return self._customers

    @property
    def billogram(self):
        """Provide access to billogram objects and attached invoices"""
        if self._billogram is None:
            self._billogram = BillogramClass(self)
        return self._billogram

    @property
    def settings(self):
        """Provide access to settings for the Billogram account"""
        if self._settings is None:
            self._settings = SingletonObject(self, 'settings')
        return self._settings

    @property
    def logotype(self):
        """Provide access to the logotype for the Billogram account"""
        if self._logotype is None:
            self._logotype = SingletonObject(self, 'logotype')
        return self._logotype

    @property
    def reports(self):
        """Provide access to the reports database"""
        if self._reports is None:
            self._reports = SimpleClass(self, 'report', 'filename')
        return self._reports

    @staticmethod
    # pylint: disable=too-many-branches
    async def _check_api_response(resp, expect_content_type=None):
        if not resp.ok or expect_content_type is None:
            # if the request failed the response should always be json
            expect_content_type = 'application/json'

        if resp.status in range(500, 600):
            # internal error
            if (resp.content_type == expect_content_type and
                    expect_content_type == 'application/json'):
                data = await resp.json()
                raise ex.ServiceMalfunctioningError(
                    'Billogram API reported a server error: {} - {}'.format(
                        data.get('status'),
                        data.get('data').get('message')
                    )
                )

            raise ex.ServiceMalfunctioningError(
                'Billogram API reported a server error'
            )

        if resp.content_type != expect_content_type:
            # the service returned a different content-type from the expected,
            # probably some malfunction on the remote end
            if resp.content_type == 'application/json':
                data = await resp.json()
                if data.get('status') == 'NOT_AVAILABLE_YET':
                    raise ex.ObjectNotAvailableYetError(
                        'Object not available yet'
                    )
            raise ex.ServiceMalfunctioningError(
                'Billogram API returned unexpected content type'
            )

        if expect_content_type == 'application/json':
            data = await resp.json()
            status = data.get('status')
            if not status:
                raise ex.ServiceMalfunctioningError(
                    'Response data missing status field'
                )
            if 'data' not in data:
                raise ex.ServiceMalfunctioningError(
                    'Response data missing data field'
                )
        else:
            # per above, non-json responses are always ok, so just return them
            return await resp.text()

        if resp.status == 403:
            # bad auth
            if status == 'PERMISSION_DENIED':
                raise ex.NotAuthorizedError(
                    'Not allowed to perform the requested operation'
                )

            if status == 'INVALID_AUTH':
                raise ex.InvalidAuthenticationError(
                    'The user/key combination is wrong, check the credentials'
                    ' used and possibly generate a new set'
                )

            if status == 'MISSING_AUTH':
                raise ex.RequestFormError('No authentication data was given')

            raise ex.PermissionDeniedError(
                'Permission denied, status={}'.format(status)
            )

        if resp.status == 404:
            # not found
            if data.get('status') == 'NOT_AVAILABLE_YET':
                raise ex.ObjectNotFoundError('Object not available yet')
            raise ex.ObjectNotFoundError('Object not found')

        if resp.status == 405:
            # bad http method
            raise ex.RequestFormError('Invalid HTTP method')

        if status == 'OK':
            return data

        errordata = data.get('data', {})

        raise {
            'MISSING_QUERY_PARAMETER': ex.RequestFormError,
            'INVALID_QUERY_PARAMETER': ex.RequestFormError,
            'INVALID_PARAMETER': ex.InvalidFieldValueError,
            'INVALID_PARAMETER_COMBINATION': ex.InvalidFieldCombinationError,
            'READ_ONLY_PARAMETER': ex.ReadOnlyFieldError,
            'UNKNOWN_PARAMETER': ex.UnknownFieldError,
            'INVALID_OBJECT_STATE': ex.InvalidObjectStateError,
        }.get(status, ex.RequestDataError)(**errordata)

    # pylint: disable=too-many-arguments
    async def fetch(
            self,
            obj,
            method,
            params=None,
            data=None,
            expect_content_type=None,
    ):
        """Perform a HTTP request to the Billogram API"""
        url = '{}/{}'.format(self._api_base, obj)
        headers = {
            'user-agent': self._user_agent,
        }
        if data:
            headers['content-type'] = 'application/json'
        response = await self._session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
        )
        await response.text()
        return await self._check_api_response(
            response, expect_content_type=expect_content_type)

    async def get(self, obj, params=None, expect_content_type=None):
        """Perform a HTTP GET request to the Billogram API"""
        return await self.fetch(
            obj, 'GET', params=params, expect_content_type=expect_content_type)

    async def post(self, obj, data):
        """Perform a HTTP POST request to the Billogram API"""
        return await self.fetch(obj, 'POST', data=json.dumps(data))

    async def put(self, obj, data):
        """Perform a HTTP PUT request to the Billogram API"""
        return await self.fetch(obj, 'PUT', data=json.dumps(data))

    async def delete(self, obj):
        """Perform a HTTP DELETE request to the Billogram API"""
        return await self.fetch(obj, 'DELETE')


class SingletonObject:
    """Represents a remote singleton object on Billogram

    Implements __getattr__ for dict-like access to the data of the remote
    object, or use the 'data' property to access the backing dict object.
    The data in this dict and all sub-objects should be treated as read-only,
    the only way to change the remote object is through the 'update' method.

    The represented object is initially "lazy" and will only be fetched on the
    first access. If the remote data are changed, the local copy can be updated
    bythe 'refresh' method.

    See the online documentation for the actual structure of remote objects.
    """
    def __init__(self, api, url_name):
        self._api = api
        self._object_class = url_name
        self._data = None

    __slots__ = ('_api', '_object_class', '_data')

    async def get(self, key):
        """Dict-like access to object data"""
        await self.data()
        return self._data.get(key)

    def __repr__(self):
        return (
            '<Billogram object \'{}\'{}>'.format(
                self._object_class,
                (self._data is None) and ' (lazy)' or ''
            )
        )

    async def url(self):
        """Get url"""
        return self._object_class

    async def data(self):
        """Access the data of the actual object"""
        if self._data is None:
            await self.refresh()
        return self._data

    async def refresh(self):
        """Refresh the local copy of the object data from remote"""
        resp = await self._api.get(await self.url())
        self._data = resp['data']
        return self

    async def update(self, data):
        """Modify the remote object with a partial or complete structure"""
        resp = await self._api.put(await self.url(), data)
        self._data = resp['data']
        return self


class SimpleObject(SingletonObject):
    """Represents a remote object on the Billogram service

    Implements __getattr__ for dict-like access to the data of the remote
    object, or use the 'data' property to access the backing dict object.
    The data in this dict and all sub-objects should be treated as read-only,
    the only way to change the remote object is through the 'update' method.

    If the remote data are changed, the local copy can be updated by
    the 'refresh' method.

    The 'delete' method can be used to remove the backing object.

    See the online documentation for the actual structure of remote objects.
    """
    def __init__(self, api, object_class, data):
        super().__init__(api, object_class)
        self._api = api
        self._object_class = object_class
        self._data = data

    __slots__ = ()

    async def url(self):
        return await self._object_class.url_of(self)

    def __getattr__(self, key):
        return self._data[key]

    async def get(self, key):
        return self._data[key]

    async def delete(self):
        """Remove the remote object from the database"""
        await self._api.delete(await self.url())


class Query:
    """Builds queries and fetches pages of remote objects

    Due to internal limitations in Billogram it is currently only possible to
    filter on a single field or special query at a time. This may change in the
    future. When it does the API will continue supporting the old filtering
    mechanism, however this client library will be updated to use the new one,
    and at that point we will strongly recommend all applications be updated.

    The exact fields and special queries available for each object type varies,
    see the online documentation for details.
    """
    def __init__(self, type_class):
        self._type_class = type_class
        self._filter = {}
        self._count_cached = None
        self._page_size = 100
        self._order = {}

    async def _make_query(self, page_number=1, page_size=None):
        query_args = {
            'page_size': page_size or self._page_size,
            'page': page_number,
        }
        query_args.update(self._get_queryargs())
        resp = await self._type_class.api.get(
            self._type_class.url_name,
            query_args,
        )
        self._count_cached = resp['meta']['total_count']
        return resp

    def _get_queryargs(self):
        args = {}
        args.update(self.filter)
        args.update(self.order)
        return args

    async def count(self):
        """Total amount of objects matched by the current query, reading this
        may cause a remote request"""
        if self._count_cached is None:
            # make a query for a single result,
            # this will update the cached count
            await self._make_query(1, 1)
        return self._count_cached

    async def total_pages(self):
        """Total number of pages required for all objects based on current
        pagesize, reading this may cause a remote request"""
        _count = await self.count()
        return (_count + self.page_size - 1) // self.page_size

    @property
    def page_size(self):
        """Number of objects to return per page"""
        return self._page_size

    @page_size.setter
    def page_size(self, value):
        value = int(value)
        assert value >= 1
        self._page_size = value
        return self

    @property
    def filter(self):
        """Filter to apply to query"""
        return self._filter

    @filter.setter
    def filter(self, value):
        if value == self._filter:
            return None
        if value:
            assert (
                'filter_type' in value and
                'filter_field' in value and
                'filter_value' in value
            )
            assert value['filter_type'] in (
                'field',
                'field-prefix',
                'field-search',
                'special',
            )
            self._filter = dict(value)
        else:
            self._filter = {}
        self._count_cached = None
        return self

    @property
    def order(self):
        """Get order """
        return self._order

    @order.setter
    def order(self, value):
        if value:
            assert 'order_field' in value and 'order_direction' in value
            assert value['order_direction'] in ('asc', 'desc')
            self._order = dict(value)
        else:
            self._order = {}
        return self

    def make_filter(
            self,
            filter_type=None,
            filter_field=None,
            filter_value=None,
    ):
        """Make complex filter"""
        if None in (filter_type, filter_field, filter_value):
            self.filter = {}
        else:
            self.filter = {
                'filter_type': filter_type,
                'filter_field': filter_field,
                'filter_value': filter_value,
            }
        return self

    def remove_filter(self):
        """Remove any filter currently set"""
        self.filter = {}
        return self

    def filter_field(self, filter_field, filter_value):
        """Filter on a basic field, look for exact matches"""
        return self.make_filter('field', filter_field, filter_value)

    def filter_prefix(self, filter_field, filter_value):
        """Filter on a basic field, look for prefix matches"""
        return self.make_filter('field-prefix', filter_field, filter_value)

    def filter_search(self, filter_field, filter_value):
        """Filter on a basic field, look for substring matches"""
        return self.make_filter('field-search', filter_field, filter_value)

    def filter_special(self, filter_field, filter_value):
        """Filter on a special query"""
        return self.make_filter('special', filter_field, filter_value)

    def search(self, search_terms):
        """Filter by a full data search
            (exact meaning depends on object type)"""
        return self.make_filter('special', 'search', search_terms)

    async def get_page(self, page_number):
        """Fetch objects for the one-based page number"""
        resp = await self._make_query(int(page_number))
        return [
            self._type_class._object_class(
                self._type_class.api,
                self._type_class,
                o
            ) for o in resp['data']
        ]

    async def iter_all(self):
        """Iterate over all matched objects"""
        # make a copy of ourselves so parameters can't be changed behind
        # our back
        qry = copy.copy(self)
        # iterate over every object on every page
        pages = await qry.total_pages()
        for page_number in range(1, pages + 1):
            page = await qry.get_page(page_number)
            for obj in page:
                yield obj


class SimpleClass:
    """Represents a collection of remote objects on the Billogram service

    Provides methods to search, fetch and create instances of the object type.

    See the online documentation for the actual structure of remote objects.
    """
    _object_class = SimpleObject

    def __init__(self, api, url_name, object_id_field):
        self._api = api
        self._url_name = url_name
        self._object_id_field = object_id_field

    async def url_of(self, obj=None, obj_id=None):
        """Get url of"""
        if obj_id is None:
            obj_id = await obj.get(self._object_id_field)
        return '{}/{}'.format(self.url_name, obj_id)

    @property
    def url_name(self):
        """Get url name"""
        return self._url_name

    @property
    def api(self):
        """Get api"""
        return self._api

    def query(self):
        """Create a query for objects of this type"""
        return Query(self)

    async def get(self, object_id):
        """Fetch a single object by its identification"""
        url = await self.url_of(obj_id=object_id)
        resp = await self.api.get(url)
        return self._object_class(self.api, self, resp['data'])

    async def create(self, data):
        """Create a new object with the given data"""
        resp = await self.api.post(self.url_name, data)
        return self._object_class(self.api, self, resp['data'])


class BillogramObject(SimpleObject):
    """Represents a billogram object on the Billogram service

    In addition to the basic methods of the SimpleObject remote object class,
    also provides specialized methods to perform events on billogram objects.

    See the online documentation for the actual structure of billogram objects.
    """
    __slots__ = ()

    async def perform_event(self, evt_name, evt_data=None):
        """Perform a generic state transition event on billogram object
        """
        url = '{}/command/{}'.format(await self.url(), evt_name)
        resp = await self._api.post(url, evt_data)
        self._data = resp['data']
        return self

    async def create_payment(self, amount):
        """Create a manual payment on billogram

        Only possible in "Unpaid" state.
        """
        assert amount > 0
        return await self.perform_event('payment', {'amount': amount})

    async def credit_amount(self, amount):
        """Credit a specific amount of the billogram

        Only possible in states "Unpaid", "Sold" and "Ended".
        """
        assert amount > 0
        return await self.perform_event(
            'credit',
            {
                'mode': 'amount',
                'amount': amount,
            }
        )

    async def credit_full(self):
        """Credit the full, original amount of the billogram

        Only possible in states "Unpaid", "Sold" and "Ended".
        """
        return await self.perform_event('credit', {'mode': 'full'})

    async def credit_remaining(self):
        """Credit the remaining unpaid amount of the billogram

        Only possible in states "Unpaid", "Sold" and "Ended".
        """
        return await self.perform_event('credit', {'mode': 'remaining'})

    async def send_message(self, message):
        """Send a message to the recipient of the billogram

        Possible from all states, except on deleted billograms.
        """
        return await self.perform_event('message', {'message': message})

    async def send_to_collector(self):
        """Send the billogram to the collection agency

        Only possible from state "Unpaid".
        """
        return await self.perform_event('collect')

    async def send_to_factoring(self):
        """Send the billogram to the factoring agency to be sold

        Only possible from state "Unattested".
        """
        return await self.perform_event('sell')

    async def send_reminder(self, method=None):
        """Send a reminder to the recipient

        'method' is the type of reminder to be sent:
         - "Email"
         - "Letter".

        Only possible from state "Unpaid".
        """
        if method:
            assert method in ('Email', 'Letter')
            return await self.perform_event('remind', {'method': method})
        return await self.perform_event('remind')

    async def send(self, method):
        """Send the billogram to the recipient

        'method' is the medium to send the billogram by:
         - "Email"
         - "Letter"
         - "Email+Letter".

        Only possible from state "Unattested".
        """
        assert method in ('Email', 'Letter', 'Email+Letter')
        return await self.perform_event('send', {'method': method})

    async def resend(self, method=None):
        """Send the billogram to the recipient again

        'method' is the medium to send the billogram by:
         - "Email"
         - "Letter".

        Only possible from state "Unpaid".
        """
        if method:
            assert method in ('Email', 'Letter')
            return await self.perform_event('resend', {'method': method})
        return await self.perform_event('resend')

    async def get_invoice_pdf(self, letter_id=None, invoice_no=None):
        """Fetch the PDF content for a specific invoice on this billogram
        """
        url = '{}.pdf'.format(await self.url())

        params = {}
        if letter_id:
            params['letter_id'] = letter_id
        if invoice_no:
            params['invoice_no'] = invoice_no
        resp = await self._api.get(
            url,
            params,
            expect_content_type='application/json'
        )
        return base64.b64decode(resp['data']['content'])

    # pylint: disable=unused-argument
    async def get_attachment_pdf(self, letter_id=None, invoice_no=None):
        """Fetch the PDF attachment for the billogram
        """
        url = '{}/attachment.pdf'.format(await self.url())

        resp = await self._api.get(url, expect_content_type='application/json')
        return base64.b64decode(resp['data']['content'])

    async def attach_pdf(self, filepath):
        """Attach a PDF to the billogram
        """
        with open(filepath) as f_pdf:
            content = f_pdf.read()

        filename = os.path.basename(filepath)
        return await self.perform_event(
            'attach',
            {
                'content': base64.b64encode(content),
                'filename': filename,
            }
        )

    async def writeoff(self):
        """Write-off remaining fees from a billogram.
        """
        return await self.perform_event('writeoff')


class BillogramQuery(Query):
    """Represents a query for billogram objects
    """

    def filter_state_any(self, *states):
        "Find billogram objects with any state of the listed ones"
        if (len(states) == 1 and isinstance(
                states[0], (list, tuple, set, frozenset))):
            states = states[0]
        assert all(isinstance(s, str) for s in states)
        return self.filter_field('state', ','.join(states))


class BillogramClass(SimpleClass):
    """Represents the collection of billogram objects on the Billogram service

    In addition to the methods of the SimpleClass collection wrapper, also
    provides specialized creation methods to create billogram objects and state
    transition them immediately.
    """
    _object_class = BillogramObject

    def __init__(self, api):
        super().__init__(api, 'billogram', 'id')

    def query(self):
        """Create a query for billogram objects"""
        return BillogramQuery(self)

    async def create_and_send(self, data, method):
        """Create the billogram and send it to the recipient in one operation

        'method' is the medium to send the billogram by:
         - "Email"
         - "Letter"
         - "Email+Letter".

        New billogram will be in state "Unpaid" or "Ended" (if the total sum
        would be zero).
        """
        assert method in ('Email', 'Letter', 'Email+Letter')
        billogram = await self.create(data)
        try:
            await billogram.send(method)
        except Exception as err:
            await billogram.delete()
            raise err
        return billogram

    async def create_and_sell(self, data):
        """Create the billogram and send it to factoring in one operation

        New billogram will be in state "Factoring".
        """
        data['_event'] = 'sell'
        billogram = await self.create(data)
        return billogram
