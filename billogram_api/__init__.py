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

""" Billogram Async API """

from billogram_api import exceptions as ex
from billogram_api.billogram_api import BillogramAPI

# make an exportable namespace-class with all the exceptions
BillogramExceptions = type(
    str('BillogramExceptions'),
    (),
    {
        nm: cl for
        nm, cl in
        ex.__dict__.items() if
        isinstance(cl, type) and issubclass(cl, ex.BillogramAPIError)
    }
)

# just the BillogramAPI class and the exceptions are really part
# of the call API of this module
__all__ = ['BillogramAPI', 'BillogramExceptions']
