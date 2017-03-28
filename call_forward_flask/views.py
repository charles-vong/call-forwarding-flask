from flask import (
    Flask,
    redirect,
    Response,
    request,
    url_for,
)
from twilio import twiml

from . import app, client
from models import (
    Senator,
    State,
    Zipcode,
)
from helpers import (
    senator_lookup_by_state,
)

@app.route('/')
def hello():
    return "Hello World, you old so and so!"

@app.route('/callcongress/welcome', methods=['POST'])
def callcongress():
    """Verify or collect State intofrmation"""
    response = twiml.Response()

    from_state = request.values.get('FromState', None)

    if from_state:
        with response.gather(numDigits=1, action='/callcongress/set-state', method='POST', from_state=from_state) as g:
            g.say('''
                Thank you for calling congress! It looks like you\'re calling from {}.
                If this is correct, please press 1.
                Press 2 if this is not your current state of residence.
            '''.format(from_state))
    else:
        with response.gather(numDigits=5, action='/callcongress/state-lookup', method='POST') as g:
            g.say('''
                Thank you for calling Call Congress! If you wish to call your senators,
                please enter your 5-digit zip code, followed by the star.
            ''')

    return Response(str(response), 200, mimetype="application/xml")

@app.route('/callcongress/state-lookup', methods=['GET', 'POST'])
def state_lookup():
    """Look up state from given zipcode.

    Once state is found, redirect to call_senators for forwarding.
    """
    # TODO: handle zips that don't map to any State
    zip_digits = request.values.get('Digits', None)
    zip_obj = Zipcode.query.filter_by(zipcode=zip_digits).first()
    state_obj = State.query.filter_by(name=zip_obj.state).first()
    return redirect(url_for('call_senators', state_id=state_obj.id))


@app.route('/callcongress/collect-zip', methods=['GET', 'POST'])
def collect_zip():
    response = twiml.Response()
    # Prompt for zipcode and redirect to state_lookup
    with response.gather(numDigits=5, action='/callcongress/state-lookup', method='POST') as g:
        g.say('''
            If you wish to call your senators, please enter your 5-digit zip code,
            followed by the star.
        ''')
    return Response(str(response), 200, mimetype="application/xml")


@app.route('/callcongress/set-state', methods=['GET', 'POST'])
def set_state():
    """Set state for senator call list:

    Set user's state from confirmation or user-provided Zip.
    Redirect to call_senators route.
    """

    # Get the digit pressed by the user
    digits_provided = request.values.get('Digits', None)
    
    # Set state if State correct, else prompt for zipcode.
    if digits_provided == '1':
        state = request.values.get('CallerState')
        state_obj = State.query.filter_by(name=state).first()
        return redirect(url_for('call_senators', state_id=int(state_obj.id)))

    elif digits_provided == '2':
        return redirect(url_for('collect_zip'))


@app.route('/callcongress/call-senators/<state_id>', methods=['GET', 'POST'])
def call_senators(state_id):
    """Route for connecting caller to both of their senators."""

    senators = State.query.get(state_id).senators.all()

    response = twiml.Response()
    response.say(
        '''Connecting you to {}. After the senator's office ends the call,
        you will be re-directed to {}.'''.format(senators[0].name, senators[1].name))
    response.dial(
        senators[0].phone,
        # TODO: hanguponstar doesn't work yet.
        hangUpOnStar=True,
        action=url_for('call_second_senator', state_id=state_id)
    )

    return Response(str(response), 200, mimetype="application/xml")

@app.route('/callcongress/call-second-senator/<state_id>', methods=['GET', 'POST'])
def call_second_senator(state_id):
    senators = State.query.get(state_id).senators.all()
    response = twiml.Response()
    response.say(
        '''Connecting you to {}.'''.format(senators[1].name))
    response.dial(
        senators[1].phone,
        hangUpOnStar=True,
    )

    return Response(str(response), 200, mimetype="application/xml")
