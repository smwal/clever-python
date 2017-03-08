try:
	from setuptools import setup
except ImportError:
	from distutils.core import setup

config = {
	'description' : 'Integrating with Clever Instant Login',
	'author' : 'Amelie Zeng',
	'url' : 'URL to get it at',
	'download_url' : 'Where to download it',
	'author_email' : 'amezen1@gmail.com',
	'version' : '0.1',
	'install_requires' : ['nose','lpthw.web','requests'],
	'packages' : ['SquidWord'],
	'scripts' : [],
	'name' : 'SquidWord'
}

setup (**config)
