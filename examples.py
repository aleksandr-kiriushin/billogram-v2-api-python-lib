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

"""Collection of examples of library usage """

import asyncio
from datetime import date, timedelta

from billogram_api import BillogramAPI, BillogramExceptions


def create_connection():
    """Create an API pseudo-connection object for the examples

    Either read configuration from a local configuration module, or from
    standard input if the module does not exist.
    """

    # Get the credentials from standard input
    # username = input("Enter API username: ").strip()
    # authkey = input("Enter API authentication key: ").strip()
    # api_urlbase = input(
    #     "API URL base (or blank for default): ").strip() or None
    username = '9843-x15fpy1h'
    authkey = '2542f158e4e649d23b892f4c1ca23725'
    api_urlbase = 'https://sandbox.billogram.com/api/v2'

    # The BillogramAPI constructor can optionally
    # take api_base and user_agent if you
    # want or need to override those, but for regular
    # production operation the defaults should be correct.
    # For testing you may have been given an
    # api_base URL for a testing environment.
    return BillogramAPI(username, authkey, api_base=api_urlbase)


async def example1(api):
    """Basic example, create, send and credit an invoice

    The invoice will be sent to customer number 1, and be for 1 unit of item 1.

    Will obviously fail if there are no customers or
        items with numbers 1 on the business account connected to.
    """
    # Make a dictionary with the data for
    # the billogram object we want to create
    # Skip non-mandatory fields in this example
    data = {
        # Specifying the recipient, must always be one from the database.
        'customer': {
            # On creation, only the customer_no can be specified.
            'customer_no': 1,
            'email': 'trash@everalerta.com',
        },
        # Specifying the items being invoiced for,
        # can either be from the database or single-use ones
        'items': [
            {
                # This item specifies just an item_no,
                # so it always uses one from the database.
                # If there is no item by this number,
                # the call will fail since other mandatory
                # fields are then missing.
                # Note that item numbers are strings,
                # they can contain non-numeric characters.
                'item_no': '1',
                # You must always specify how many of
                # each item is being invoiced for.
                'count': 1,

                'price': 1899.32,

                # title is required parameter
                'title': 'item_example',
            }
        ],
        # The inovoicing currency must always be given,
        # although currently only SEK is supported.
        'currency': 'SEK',
        # Have the due date be 35 days (5 weeks) in the future
        'due_date': (date.today() + timedelta(days=35)).isoformat()
    }

    print('Creating and sending billogram with data:\n{}'.format(
            prettyfy(data)))

    try:
        # Attempt to create and then send the billogram using the data.
        # If this succeeds, the result will be a billogram object,
        # wrapping a dictionary with the state of
        # the billogram after the two operations.
        billogram = await api.billogram.create_and_send(data, 'Email')
        print("The result of creating the billogram object:\n{}".format(
                prettyfy(await billogram.data())))

        print("Now crediting the entire billogram (id {})".format(
                await billogram.get('id')))
        # Credit the billogram, creates a new state in the
        # billogram object and sends a credit invoice to the recipient.
        # The object is updated with the new state after the operation.
        await billogram.credit_full()
        print('State of billogram after crediting:\n{}'.format(
                prettyfy(await billogram.data())))

    # pylint: disable=no-member
    except BillogramExceptions.BillogramAPIError as err:
        print('An API error occurred: {!r}'.format(err))


async def example2(api):
    """Find all "gadget" items and increase their price by 10%
    """
    # First create a query object for the items class
    qry = api.items.query()
    # Set up some query parameters
    # items with "gadget" in somewhere their title
    qry.filter_search('title', 'gadget')

    # print some status
    count = await qry.count()
    print('Matched {} gadget items to change'.format(count))

    # Loop over every page of results, processing all items
    async for item in qry.iter_all():
        print('Current price for item {} is {}'.format(
                item['item_no'], item['price']))
        # modify the item
        await item.update({
            'price': round(item['price']*1.1, 2)
        })
        print('    New price is {}'.format(item['price']))


async def example3(api):
    """Create or find a customer and invoice them
    """
    customer_no = 12345
    try:
        print('Trying to fetch customer {}'.format(customer_no))
        customer = await api.customers.get(customer_no)
        print('Found the customer')

    # pylint: disable=no-member
    except BillogramExceptions.ObjectNotFoundError:
        print('Customer not found, creating instead')
        customer_data = {
            'customer_no': customer_no,
            'name': 'Terkel Testsson',
            'contact': {
                'name': 'Terkel Testsson',
                'email': 'terkel@example.com',
            },
            'address': {
                'street_address': 'Exempelgatan 123',
                'city': 'Stockholm',
                'zipcode': '123 45',
                'country': 'SE',
            },
            'company_type': 'individual',
        }
        customer = await api.customers.create(customer_data)
        print('Customer was created')

    print('Trying to create billogram object')
    billogram_data = {
        'customer': {
            'customer_no': customer_no,
        },
        'items': [
            {
                'title': 'Customer assistance',
                'description': (
                    'Phone conversation and physical warehouse search'
                ),
                'price': 300,
                'unit': 'hour',
                'vat': 25,
                'count': 0.5,
            },
            {
                'item_no': '20',
                'description': 'Adding 0.14 extra for your convenience',
                'count': 3.14,
                'title': 'item_example',  # title is required parameter
            },
        ],
        'currency': 'SEK',
        'invoice_fee': 50,
        'due_date': (date.today() + timedelta(days=30)).isoformat(),
        'automatic_reminders': False,
    }
    billogram = await api.billogram.create(billogram_data)
    print('Billogram object created, id is {}'.format(
            await billogram.get('id')))

    await customer.update(
        {
            'notes': 'Last conversation was on invoice id {}'.format(
                await billogram.get('id')
            )
        }
    )
    print('Customer object updated before sending invoice')

    await billogram.send('Email+Letter')
    print('Invoice has now been sent')


async def example4(api):
    """Find a fully paid or credited invoice and download all its PDF documents
    """
    print('Querying for paid or credited billogram objects')
    query = api.billogram.query()
    query.filter_state_any('Paid', 'Credited')
    query.page_size = 1
    bgs = await query.get_page(1)
    if not bgs:
        print('No billogram found')
        return
    billogram = bgs[0]
    bg_data = await billogram.data()
    print('Found billogram with id {0[id]}, state is {0[state]}'.format(
            bg_data))
    print('Getting full information for billogram object')
    # the object is initially a compact one,
    # refreshing it will get the full data
    await billogram.refresh()
    print('Now processing events')
    for event in bg_data.get('events', []):
        print('{0[type]} event at {0[created_at]}'.format(event))
        if event['data'] and 'letter_id' in event['data']:
            print(
                '  - has letter_id {0[data][letter_id]}, getting it'.format(
                    event
                )
            )
            # pylint: disable=no-member
            try:
                pdf = await billogram.get_invoice_pdf(
                        letter_id=event['data']['letter_id'])
                print('  - pdf is {} bytes long'.format(len(pdf)))
            except BillogramExceptions.ObjectNotAvailableYetError:
                print('  - pdf not created yet')
            except BillogramExceptions.ObjectNotFoundError:
                print('  - pdf was not found')


async def example5(api):
    """This example shows some error handling
    """
    # A billogram dataset containing invalid items
    billogram_data = {
        'customer': {
            'customer_no': 12345
        },
        'items': [
            # This item (0) is fine
            {
                'title': 'Test 1',
                'price': 1,
                'unit': 'unit',
                'vat': 25,
                'count': 1,
            },
            # This one (1) is fine too
            {
                'title': 'Test 2',
                'price': -2,
                'unit': 'kg',
                'vat': 0,
                'count': 1,
            },
            # Error here (2), no title
            {
                'price': 3,
                'unit': 'kg',
                'vat': 0,
                'count': 1,
            },
            # Error here too (3), missing count
            {
                'title': 'Test 4',
                'price': -10,
                'vat': 0,
            },
        ],
        'currency': 'SEK',
        'due_date': (date.today() + timedelta(days=30)).isoformat(),
    }
    # Attempt creating it
    try:
        print('Trying to create invalid billogram')
        await api.billogram.create(billogram_data)
        print('Billogram created?! This should not happen.')
    # pylint: disable=no-member
    except BillogramExceptions.RequestDataError as err:
        print('Creating the billogram failed! Exception is {}'.format(
                err.__class__.__name__))
        if err.message:
            print('The error message returned is: {}'.format(err.message))
        if err.field:
            print('The field name is \'{}\''.format(err.field))
        if err.field_path:
            print(
                'Additionally, the error is located in '
                'this sub-object: {}'.format(err.field_path)
            )
        print(
            'The expected error is \'Title not set\', in '
            'the \'title\' field of [\'items\', 2]'
        )


# From here on it's just housekeeping, no more examples


# Helper function to pretty-print the structures
def prettyfy(obj, level=''):
    """Print pretty """
    nextlevel = level + '  '
    if isinstance(obj, dict):
        return '{\n' + ',\n'.join(['{}{!s}: {}'.format(
                nextlevel, k, prettyfy(v, nextlevel)
        ) for k, v in obj.items()]) + '\n' + level + '}'
    if isinstance(obj, list):
        return '[\n' + ',\n'.join(['{}{}'.format(
            nextlevel, prettyfy(v, nextlevel)
        ) for v in iter(obj)]) + '\n' + level + ']'
    if isinstance(obj, set):
        return '{\n' + ',\n'.join(['{}{}'.format(
            nextlevel, prettyfy(v, nextlevel)
        ) for v in iter(obj)]) + '\n' + level + '}'
    if isinstance(obj, tuple):
        return '(\n' + ',\n'.join(['{}{}'.format(
            nextlevel, prettyfy(v, nextlevel)
        ) for v in iter(obj)]) + '\n' + level + ')'
    return repr(obj)


async def main():
    """Run examples"""
    print('Billogram v2 API examples')
    async with create_connection() as api:
        print('Running example 1')
        await example1(api)
        print()

        print('Running example 2')
        await example2(api)
        print()

        print('Running example 3')
        await example3(api)
        print()

        print('Running example 4')
        await example4(api)
        print()

        print('Running example 5')
        await example5(api)
        print()

    print('Finished running all examples')

# For running the examples from a terminal
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
