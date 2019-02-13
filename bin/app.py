import web
import os
import requests

urls = (
	'/', 'Index',
	'/oauth/clever/','IL', #makes a valid redirect URI
	'/home/','home' # a page for logged-in users
)

client_id=os.environ['CLEVER_CLIENT_ID']
client_secret=os.environ['CLEVER_CLIENT_SECRET']
redirect_uri="https://squidword.herokuapp.com/oauth/clever/"

app = web.application(urls, globals())

render = web.template.render('templates/', base="layout")

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
	print r.text
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
	print "POST attempt failed"
	return None

# This Class defines users as they log in. The most important information we'll need for each
# user is their Clever ID ('id'), District ID ('district'), and user type ('type')
class User(object):

	cleverID = None
	districtID = None
	user_type = None

	endpoint = None
	token = None
	name = {'first':None, 'middle':None,'last':None}

	# using __new__ instead of __init__ because I want to be able to abort the creation process
	def __new__(self, response, token):
		self.token = token

		print
		# Pulling Clever ID, District ID and User Type from the JSON response
		self.cleverID = response['data']['id']
		# self.districtID = response['data']['district'] // Removing requirement because library responses don't contain district ID
		self.user_type = response['data']['type']

		# Getting the right endpoint in the Data API for the user's Type
		if self.user_type in {'student', 'teacher', 'school_admin', 'district_admin'}:
			# Note the first placeholder is '%ss' - user_type is singular, but the endpoints
			# use the plural form
			self.endpoint = 'https://api.clever.com/v1.1/%ss/%s' % (self.user_type, self.cleverID)

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
			print "Failure :("
			return None
		print "Success!"

		# First name and last name are required fields in the API, so I don't need to do 
		# any checks to make sure that this data exists - no users will exist without
		# first and last name
		self.name['first'] = r['data']['name']['first']
		self.name['last'] = r['data']['name']['last']

		# Middle name is optional, so we check to make sure it exists before attempting
		# to pull that data from the JSON object. If not, leave that as None
		if 'middle' in r['data']['name']:
			self.name['middle'] = r['data']['name']['middle']

		return self

	# Because I'm handling all user creation tasks in __new__, this is just to confirm that 
	# the user's been created
	def __init__(self):
		print "Successful user creation!"

# This class defines the page at http://localhost:8080/ - currently a form to fill out, but
# will soon contain the homepage for SquidWord!
class Index(object):
	def GET(self):
		return render.index()

# This class defines what happens when the Instant Login flow is initiated - when a user is
# redirected to my redirect URI
class IL(object):

	def GET(self):
		# When a user is redirected to my URI, Clever should append a code and scopes to the
		# URI (?code=<code>&scopes=<scopes>). Here, I am grabbing the code and scopes from the
		# URI so I can use them to complete the OAuth Authorization Code flow. If the expected
		# code is not provided, the value of each will be set to None so the user will not see
		# an error
		form = web.input(code=None,scope=None)	

		# On the off chance that someone is just accessing /oauth/clever/ directly (the Clever
		# team will sometimes do this to check and see if the URI is available during issue
		# troubleshooting) or if no code is provided, there's no point in attempting to 
		# get a token. This should show an error message and ideally allow users to click to 
		# attempt a new login
		if form.code==None:
			return "No Valid Code"
		
		# Now that we have a valid code, we can exchange it for a bearer token.
		ilToken = getToken(form.code)

		# If the token exchange fails, the user will not be able to log in. The exchange
		# can fail if:
		# 	* My client id and secret don't match what's in Clever's database
		#	* The code has expired (codes are valid for five minutes)
		#	* The code has already been successfully exchanged for a token
		#	* Clever is down
		if ilToken == None:
			return "Token request fail"
		print "Received Token %s" % (ilToken)

		me = cleverGET('https://api.clever.com/me/',ilToken)
				
		print me

		if me == None:
			return "Request failed :("

		newUser = User(me, ilToken)

		firstName = newUser.name['first']
		userType = newUser.user_type

		return render.home(firstName,userType)


if __name__ == "__main__":
    app.run()
