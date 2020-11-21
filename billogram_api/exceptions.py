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

""" Exceptions for library for asynchronous accessing the Billogram v2 HTTP API
"""


class BillogramAPIError(Exception):
    """Base class for errors from the Billogram API"""
    def __init__(self, message, **kwargs):
        super().__init__(message)
        self.message = message

        self.field = kwargs.get('field', None)
        self.field_path = kwargs.get('field_path', None)

        self.extra_data = kwargs
        if 'field' in self.extra_data:
            del self.extra_data['field']
        if 'field_path' in self.extra_data:
            del self.extra_data['field_path']
        if not self.extra_data:
            self.extra_data = None


class ServiceMalfunctioningError(BillogramAPIError):
    """The Billogram API service seems to be malfunctioning"""


class RequestFormError(BillogramAPIError):
    """Errors caused by malformed requests"""


class PermissionDeniedError(BillogramAPIError):
    """No permission to perform the requested operation"""


class InvalidAuthenticationError(PermissionDeniedError):
    """The user/key combination could not be authenticated"""


class NotAuthorizedError(PermissionDeniedError):
    """The user does not have authorization
        to perform the requested operation"""


class RequestDataError(BillogramAPIError):
    """Errors caused by bad data passed to request"""


class UnknownFieldError(RequestDataError):
    """An unknown field was passed in the request data"""


class MissingFieldError(RequestDataError):
    """A required field was missing from the request data"""


class InvalidFieldCombinationError(RequestDataError):
    """Mutually exclusive fields were specified together"""


class InvalidFieldValueError(RequestDataError):
    """A field was given an out-of-range value or a value of incorrect type"""


class ReadOnlyFieldError(RequestDataError):
    """Attempt to modify a read-only field"""


class InvalidObjectStateError(RequestDataError):
    """The request can not be performed on an object in this state"""


class ObjectNotFoundError(RequestDataError):
    """No object by the requested ID exists"""


class ObjectNotAvailableYetError(ObjectNotFoundError):
    """No object by the requested ID exists,
        but is expected to be created soon"""
