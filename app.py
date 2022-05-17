from flask import Flask, request, render_template, session, redirect, url_for
from urllib.parse import quote
import os
import requests
import hashlib

# Get Clever credentials
client_id = os.getenv('CLEVER_CLIENT_ID')
client_secret = os.getenv('CLEVER_CLIENT_SECRET')

app = Flask(__name__)

# Secret key needed for using sessions
app.secret_key = os.getenv('SECRET_KEY')

base_url = os.getenv('BASE_URL')
redirect_uri = base_url + '/oauth/clever/'
uri_encoded = quote(redirect_uri, safe='')
auth_link = 'https://clever.com/oauth/authorize?response_type=code&redirect_uri=%s&client_id=%s' % (uri_encoded, client_id)



# POST-ing to Clever. In this integration, this is only used for exchanging Authorization 
# Codes for IL Bearer Tokens
#
# This function returns the full response, and a separate function (getToken) extracts the token
def cleverPOST(endpoint, data):
	r = requests.post(endpoint, data=data, auth=(client_id, client_secret))
	return r

# GET-ting information from the Clever API. In this integration, this is used both to GET
# basic information about the user from the Identity API and to query the Data API for user
# data.
#
# This funtion returns the API response as a JSON object. Separate functions are used to 
# process the data thereafter
def cleverGET(endpoint, token):
	headers = {
		"Authorization":"Bearer %s" % token
	}
	
	r = requests.get(endpoint, headers=headers)

	if r.status_code == 200:
		return r.json()
	print(r.text)
	return None

# This function takes in a code from the redirect URI and attempts to exchange it for a 
# bearer token.
def getToken(code):
	api_endpoint = 'https://clever.com/oauth/tokens'
	data = {
		"code":code,
		"grant_type":"authorization_code",
		"redirect_uri":redirect_uri
	}

	r = cleverPOST(api_endpoint, data)
	
	if r.status_code == 200:
		token = r.json()['access_token']
		return token
	print("POST attempt failed")
	return None

# This function generates a random state value to protect against Cross-Site Request Forgery (CSRF)
def new_state():
    state = hashlib.sha256(os.urandom(1024)).hexdigest()
    session['state'] = state
    return state

# This Class defines users as they log in. The most important information we'll need for each
# user is their Clever ID ('id') and user type ('type')
class User(object):

	userID = None
	user_type = None
	user_role = None

	endpoint = None
	token = None
	name = {'first':None, 'middle':None,'last':None}

	# using __new__ instead of __init__ because I want to be able to abort the creation process
	def __new__(self, response, token):
		self.token = token

		# Pulling Clever ID and User Type from the JSON response
		self.userID = response['data']['id']
		self.user_type = response['data']['type']

		# Getting the right endpoint in the Data API for the user's Type
		if self.user_type in {'user'}:
			# Note the first placeholder is '%ss' - user_type is singular, but the endpoints
			# use the plural form
			self.endpoint = 'https://api.clever.com/v3.0/%ss/%s' % (self.user_type, self.userID)

		# Redirect_uris are multi-use - with this if case, I'm cancelling user creation in the
		# case where the user type is 'district' (for new district authorizations) or an 
		# unexpected user type. 
		#
		# For new district authorizations, there is no actual user logging in, so I'm 
		# comfortable with throwing this error. For new user types, Clever will make developers 
		# aware well in advance, so I can add any additional user types before users will see 
		# this error message
		if self.endpoint == None:
			raise ValueError

		# Now that I know which endpoint has the data I'm looking for, I'll query for this 
		# user's data
		r = cleverGET(self.endpoint, self.token)

		if r == None:
			print("Failure :(")
			return None
		print("Success!")

		# First name and last name are required fields in the API, so I don't need to do 
		# any checks to make sure that this data exists - no users will exist without
		# first and last name
		self.name['first'] = r['data']['name']['first']
		self.name['last'] = r['data']['name']['last']

		# Middle name is optional, so we check to make sure it exists before attempting
		# to pull that data from the JSON object. If not, leave that as None
		if 'middle' in r['data']['name']:
			self.name['middle'] = r['data']['name']['middle']

		self.user_roles = r['data']['roles']
		self.user_role = None

		if 'student' in self.user_roles:
			self.user_role = 'student'
		elif 'teacher' in self.user_roles:
			self.user_role = 'teacher'
		elif 'staff' in self.user_roles:
			self.user_role = 'staff'	
		elif 'district_admin' in self.user_roles:
			self.user_role = 'district admin'

		return self

	# Because I'm handling all user creation tasks in __new__, this is just to confirm that 
	# the user's been created
	def __init__(self):
		print("Successful user creation!")

# This is the first page a user sees, and also the page a user will be redirected to if they try to access
# other pages and are not logged in. It sets a login link using a randomly generated state value.
@app.route('/')
def index():
    state = new_state()
    return render_template('index.html', auth_link = '%s&state=%s' % (auth_link, state))

# This route defines the behavior at the redirect URI. After checking a valid state parameter is included, the
# auth code from Clever is exchanged for a bearer token. This token is then used to get information about 
# the user, and if everything is successful the user is redirected to the home page.
@app.route('/oauth/clever/')
def code_exchange():
    # Check to make sure state matches the value stored for this user. If there is no state parameter 
    # (Clever-initiated login link), re-redirect after adding state parameter
    state = request.args.get('state', None)
    if not state:
        state = new_state()
        return redirect('%s&state=%s' % (auth_link, state))
    elif state != session['state']:
        return 'Invalid state parameter', 401
    
    # When a user is redirected to my URI, Clever should append a code and scopes to the
	# URI (?code=<code>&scopes=<scopes>). Here, I am grabbing the code from the
	# URI so I can use it to complete the OAuth Authorization Code flow. If the expected
	# code is not provided, the value of each will be set to None so the user will not see
	# an error
    code = request.args.get('code', None)
	
    # On the off chance that someone is just accessing /oauth/clever/ directly (the Clever
	# team will sometimes do this to check and see if the URI is available during issue
	# troubleshooting) or if no code is provided, there's no point in attempting to 
	# get a token. This should show an error message and ideally allow users to click to 
	# attempt a new login
    if code == None:
        return "No Valid Code"
		
	# Now that we have a valid code, we can exchange it for a bearer token.
    ilToken = getToken(code)

	# If the token exchange fails, the user will not be able to log in. The exchange
	# can fail if:
	# 	* My client id and secret don't match what's in Clever's database
	#	* The code has expired (codes are valid for five minutes)
	#	* The code has already been successfully exchanged for a token
	#	* Clever is down
    if ilToken == None:
        return "Token request fail"
    print("Received Token %s" % ilToken)

    me = cleverGET('https://api.clever.com/v3.0/me/',ilToken)
				
    print(me)

    if me == None:
        return "Request failed :("

    newUser = User(me, ilToken)

    # Store user info in the session so it can be accessed by all pages
    session['firstName'] = newUser.name['first']
    session['userRole'] = newUser.user_role

    # Redirect to home page
    return redirect(url_for('home'))


@app.route('/home')
def home():
    # If no user logged in, redirect to main page for logging in
    if 'firstName' not in session:
        return redirect(url_for('index'))

    return render_template('home.html', firstName=session['firstName'], userRole=session['userRole'])

if __name__ == '__main__':
    app.run(threaded=True, port=5000)