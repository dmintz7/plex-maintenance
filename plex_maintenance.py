from flask import Flask, request, make_response
from plexapi.server import PlexServer
from logging.handlers import RotatingFileHandler
import os, subprocess, logging, sys, config, json, re

plex = PlexServer(config.plex_host, config.plex_api)
app = Flask(__name__)

logger = logging.getLogger('root')
formatter = logging.Formatter('%(asctime)s - %(levelname)10s - %(module)15s:%(funcName)30s:%(lineno)5s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)	
logger.addHandler(consoleHandler)
logging.getLogger("requests").setLevel(logging.INFO)
logger.setLevel(config.log_level.upper())
fileHandler = RotatingFileHandler(config.log_folder + "/plex-maintenance.log", maxBytes=1024 * 1024 * 2, backupCount=1)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)

@app.route('/', methods=['POST'])
def api_command():
	json_text = request.get_json()
	logger.debug("Received API Command - %s" % json_text)
	(section_id, event, directory, title) = parese_json(json_text)
	logger.debug((section_id, event, directory, title))
	if event == 'Test':
		get_plex_duplicates()
		section_id = None
		logger.info("Test Command Received")

	if section_id is not None:
		try:
			try:
				rep = dict((re.escape(k), v) for k, v in json.loads(config.remote_mapping).items()) 
				pattern = re.compile("|".join(rep.keys()))
				directory = pattern.sub(lambda m: rep[re.escape(m.group(0))], directory)
			except:
				pass
			
			command = '%s --scan --refresh --section %s --directory "%s"' % (config.plex_media_scanner_path, section_id, directory)
			logger.debug("Running Command - %s" % command)
			logger.info("Adding %s to Plex" % title)
			process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
			process.wait()
			logger.debug("Adding to Plex, Finished")
			if (event == 'Download' and json_text['isUpgrade']) or event == 'Rename': get_plex_duplicates()
		except Exception as e:
			logger.error('Error on line {} - {} - {}'.format(type(e).__name__, sys.exc_info()[-1].tb_lineno, e))
	return make_response("", 200)

def create_plex_title(video):
	if video.type == "movie":
		try:
			title = "%s (%s)" % (video.title, video.originallyAvailableAt.strftime("%Y"))
		except:
			title = video.title
	else:
		title = "%s - %s - %s" % (video.grandparentTitle, video.parentTitle, video.title)
	return title

def get_plex_duplicates():
	exists = []
	missing = []
	duplicates = []
	logger.debug("Checking for Duplicates")
	for section in plex.library.sections():
		if section.TYPE in ('movie'):
			duplicates = duplicates + section.search(duplicate=True)
		elif section.TYPE in ('show'):
			duplicates = duplicates + section.searchEpisodes(duplicate=True)
	for dup in duplicates:
		try:
			if len(dup.locations) > 1:
				parts = create_media_lists(dup)
				for media, video in parts:
					if os.path.exists(video.file):
						logger.debug("Adding %s to existing" % video.file)
						exists.append(create_plex_title(dup))
					else:
						logger.debug("Adding %s to missing" % video.file)
						missing.append((media, video, dup))
		except:
			pass

	if len(missing) > 0:
		for media, video, dup in missing:
			try:
				if create_plex_title(dup) in exists:
					logger.info("File (%s) missing from Plex Database, Removing Due to Duplicate" % video.file)
					if not os.path.exists(video.file): media.delete()
			except:
				pass
				
def create_media_lists(movie):
	try:
		patched_items = []
		for zomg in movie.media:
			zomg._initpath = movie.key
			patched_items.append(zomg)
		zipped = zip(patched_items, movie.iterParts())
		parts = sorted(zipped, key=lambda i: i[1].size if i[1].size else 0, reverse=True)
		return parts
	except:
		return None

def parese_json(json_text):
	try:
		event = json_text['eventType']
		if event == 'Test':
			section_id = 1
			directory = "Test"
			title = "Test"
		elif 'movie' in json_text:
			section_id = config.movie_section_id
			directory = json_text['movie']['folderPath']
			if event == 'Rename':
				title = json_text['movie']['title']
			else:
				title = "%s (%s) - %s" % (json_text['movie']['title'], json_text['remoteMovie']['year'], json_text['movieFile']['quality'])
		elif 'series' in json_text:
			section_id = config.tv_section_id
			directory = json_text['series']['path']
			show_title = json_text['series']['title']
			if event == 'Rename':
				title = show_title
			else:
				episode_title = json_text['episodes'][0]['title']
				season = json_text['episodes'][0]['seasonNumber']
				episode = json_text['episodes'][0]['episodeNumber']
				quality = json_text['episodeFile']['quality']
				title = "%s - S%sE%s - %s - %s" % (show_title, season, episode, episode_title, quality)
		else:
			section_id = 0
	except Exception as e:
		logger.error('Error on line {} - {} - {}'.format(type(e).__name__, sys.exc_info()[-1].tb_lineno, e))
		section_id = 0
	
	if int(section_id) > 0:
		return (section_id, event, directory, title)
	else:
		return (0, None, None, None)