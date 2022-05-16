Create a Clever dev application and set the redirect URI to `http://127.0.0.1:5000/oauth/clever/`. Enable all user types.

Clone the repository using the following command:
`git clone https://github.com/zwalchuk/squidword.git`

Navigate to the repo:
`cd squidword/`

Create a virtual environment:
`python3 -m venv venv`

Activate the virtual environment:
`source venv/bin/activate`

Install supporting libraries:
`pip install Flask`
`pip install requests`

Set your Clever app credentials as environment variables:
`export CLEVER_CLIENT_ID=<your client id>`
`export CLEVER_CLIENT_SECRET=<your client secret>`

Set additional environment variables:
`export BASE_URL="http://127.0.0.1:5000"`
`export SECRET_KEY=<random string>`


Back in your terminal, kick off the `app.py` script:
`python app.py`

Navigate to `http://127.0.0.1:5000` in your browser, then try logging in with a Clever Library user (district 5b2ad81a709e300001e2cd7a)