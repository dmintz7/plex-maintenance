import os, sys, shutil
from pathlib import Path

origin_repo="https://github.com/${git_owner:-dmintz7}/plex-maintenance"
variables = {
	"root_dir": {"description": "Directory to install into", "default" :"", "user_input" : ""},
	"log_folder": {"description": "Directory to save logs into", "default" : "", "user_input" : ""},
    "log_level": {"description": "Logging Level (This can be changed later)", "default" : "info", "user_input" : ""},
    "movie_section_id": {"description": "ID for Movie Library", "default" : "", "user_input" : ""},
    "tv_section_id": {"description": "ID for TV Library", "default" : "", "user_input" : ""},
    "plex_host": {"description": "Plex Server IP/DNS name", "default" : "http://127.0.0.1:32400", "user_input" : ""},
    "plex_api": {"description": "Plex API Token", "default" : "", "user_input" : ""},
    "plex_media_scanner_path": {"description": "Path to Plex Media Scanner", "default" : "", "user_input" : ""},
    "remote_mapping": {"description": "Remote Mapping", "default" : "", "user_input" : ""},
    "plex_user": {"description": "User that runs Plex Media Server", "default" : "", "user_input" : ""},
    "bind_address": {"description": "Bind Address and Port for plex-maintenance", "default" : "0.0.0.0:32500", "user_input" : ""},
}

def install():
	if not os.path.exists(variables['root_dir']['user_input']):
		print("Installing plex-maintenance into '%s'... " % variables['root_dir']['user_input'])
		os.system('git clone --branch "master" "%s" "%s"' % (origin_repo, variables['root_dir']['user_input']))
		
		if not os.path.exists(variables['log_folder']['user_input']): os.makedirs(variables['log_folder']['user_input'])
		print("Done")
		return True
	else:
		print("plex-maintenance already installed, Updating")
		os.system('git pull')
		return False

def createFile():
	files = {
		"config": {
			"file": str(Path(variables['root_dir']['user_input']+"/config.py")),
			"quote_enclosed" : True,
			"lines" :(
				("log_level=","log_level"),
				("log_folder=","log_folder"),
				("movie_section_id=","movie_section_id"),
				("tv_section_id=","tv_section_id"),
				("plex_host=","plex_host"),
				("plex_api=","plex_api"),
				("plex_media_scanner_path=","plex_media_scanner_path"),
				("remote_mapping=","remote_mapping"),
			)
		},
		"service": {
			"file": "/lib/systemd/system/plex-maintenance.service",
			"quote_enclosed" : False,
			"lines" :(
				("[Unit]",""),
				("Description=Plex Maintenance",""),
				("After=plexmediaserver.service",""),
				("[Service]",""),
				("User=","plex_user"),
				("WorkingDirectory=","root_dir"),
				("ExecStart=uwsgi --ini plex-maintenance.ini",""),
				("[Install]",""),
				("WantedBy=multi-user.target",""),
			)
		},
		"uwsgi": {
			"file": str(Path(variables['root_dir']['user_input']+"/plex-maintenance.ini")),
			"quote_enclosed" : False,
			"lines" :(
				("[uwsgi]",""),
				("module = plex-maintenance:app",""),
				("master = true",""),
				("processes = 5",""),
				("http = ","bind_address"),
				("socket = /tmp/plex-maintenance.sock",""),
				("chmod-socket = 660",""),
				("vacuum = true",""),
				("die-on-term = true",""),
			)
		}
	}

	for key, value in files.items():
		f = open(value['file'] + '.tmp', "a")
		for line, variable in value['lines']:
			temp = (variables[variable]['user_input'] if variable else "")
			if value['quote_enclosed']: temp = '"%s"' % temp
			f.write("%s%s\n" % (line, temp))
		f.close()
		shutil.move(value['file'] + '.tmp', value['file'])

def ask_user(question):
	check = str(input(question + " (Y/N): ")).lower().strip()
	try:
		if check[0] == 'y':
			return True
		elif check[0] == 'n':
			return False
		else:
			print('Invalid Input')
			return ask_user(question)
	except Exception as error:
		print("Please enter valid inputs")
		print(error)
		return ask_user(question)
		
def createRemoteMapping():
	remote_mapping = dict()
	if ask_user("Would you like to setup remote paths?  "):
		while True:
			remote_path = input("Enter Remote Path:  ").strip()
			local_path = input("Enter Local Path:   ").strip()
			remote_mapping[remote_path] = local_path
			if not ask_user("Add Another?  "): break
	return remote_mapping

def assignVariables():
	if sys.platform == "linux" or sys.platform == "linux2":
		for key, value in variables.items():
			if key == "root_dir": value['default'] =  "/opt/plex-maintenance"
			if key == "plex_user": value['default'] =  "plex"
			if key == "log_folder": value['default'] =  str(Path(variables['root_dir']['default'] + "/logs"))
			if key == "plex_media_scanner_path": value['default'] =  str(Path("/usr/lib/plexmediaserver/Plex\ Media\ Scanner"))
	else:
		print("Your OS is Not Supported")
		sys.exit()

	for key, value in variables.items():
		while True:
			if key == "remote_mapping":
				value['user_input'] = createRemoteMapping()
				break
			else:
				value['user_input'] = input(value['description'] + (": (" + value['default'] + ")  " if value['default'] else ":  ")) or value['default']
			if value['default'] or value['user_input']:
				if not value['user_input']: value['user_input'] = value['default']
				break

assignVariables()
install()
createFile()
os.system("sudo systemctl daemon-reload")
os.system("sudo systemctl enable plex-maintenance.service")
print("Starting Service")
os.system("sudo systemctl start plex-maintenance.service")