import os, sys
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
    "bind_address": {"description": "Bind Address and Port for plex-maintenance", "default" : "127.0.0.1:3500", "user_input" : ""},
}

def install():
	if not os.path.exists(variables['root_dir']['user_input']):
		print("Installing plex-maintenance into '%s'... " % variables['root_dir']['user_input'])
		os.system('git clone --branch "master" "%s" "%s"' % (origin_repo, variables['root_dir']['user_input']))
		
		os.makedirs(variables['log_folder']['user_input'])
		print("Done")
	else:
		print("plex-maintenance already installed")

def createFile():
	files = {
		"config": {
			"file": str(Path(variables['root_dir']['user_input']+"/config.py")),
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
		"lines" :(
			("[uwsgi]",""),
			("module = plex_maintenance:app",""),
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
		f = open(value['file'], "a")
		for line, variable in value['lines']:
			f.write(line + (variables[variable]['user_input'] if variable else "") + '\n')
		f.close()

def createRemoteMapping():
	remote_mapping = dict()
	while True:
		remote_path = input("Enter Remote Path:  ").strip()
		if remote_path == '': break
		local_path = input("Enter Local Path:  ").strip()
		remote_mapping[remote_path] = local_path
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
		if key == "remote_mapping":
			createRemoteMapping()
		else:
			while True:
				value['user_input'] = input(value['description'] + (": (" + value['default'] + ")  " if value['default'] else ":  ")) or value['default']
				if value['default'] or value['user_input']:
					value['user_input'] = value['default']
					break

assignVariables()
install()
createFile()
os.system("chown $(id ${%s} -u):$(id ${%s} -g) -R '%s'" % (variables['plex_user']['user_input'], variables['plex_user']['user_input'], variables['root_dir']['user_input']))
