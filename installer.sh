#!/bin/bash

ORIGIN_REPO="https://github.com/${GIT_OWNER:-dmintz7}/plex-maintenance"
FULL_PATH="/opt/plex-maintenance"

# variables to save in config
CONFIGVARS="log_level log_folder movie_section_id tv_section_id plex_host plex_api plex_media_scanner_path remote_mapping"
CONFIGFILE="${FULL_PATH}/config.py"
SERVICEFILE="/lib/systemd/system/plex-maintenance.service"

# set default variables
log_level="info"

install() {
	echo
	read -e -p "Directory to install into: " -i "/opt/plex-maintenance" FULL_PATH

	while [[ "$FULL_PATH" == *"~"* ]]; do
		echo "Using '~' in your path can cause problems, please type out the full path instead"
		echo
		read -e -p "Directory to install into: " -i "/opt/plex-maintenance" FULL_PATH
	done

	if [ ! -d "$FULL_PATH" ]; then
		echo -n "'$FULL_PATH' doesn't exist, attempting to create... "
		echo 
		if ! mkdir -p "$FULL_PATH" 2>/dev/null; then
			sudo mkdir -p "$FULL_PATH" || abort "failed, cannot continue"
			sudo chown $(id -u):$(id -g) "$FULL_PATH" || abort "failed, cannot continue"
		fi
		echo "done"
	elif [ ! -w "$FULL_PATH" ]; then
		echo -n "'$FULL_PATH' exists, but you don't have permission to write to it. Changing owner... "
		sudo chown $(id -u):$(id -g) "$FULL_PATH" || abort "failed, cannot continue"
		echo "done"
	fi

	if [ -d "${FULL_PATH}/.git" ]; then
		cd "$FULL_PATH"
		if git remote -v 2>/dev/null | grep -q "plex-maintenance"; then
			echo -n "Found existing plex-maintenance repository in '$FULL_PATH', updating... "
			if [ -w "${FULL_PATH}/.git" ]; then
				git pull &>/dev/null || abort "unknown error while updating, please check '$FULL_PATH' and then try again."
			else
				sudo git pull &>/dev/null || abort "unknown error while updating, please check '$FULL_PATH' and then try again."
			fi
		else
			abort "'$FULL_PATH' appears to contain a different git repository, cannot continue"
		fi
		echo "done"
		cd - &> /dev/null
	else
		echo -n "Installing plex-maintenance into '$FULL_PATH'... "
		git clone --branch "${BRANCHNAME:-master}" "$ORIGIN_REPO" "$FULL_PATH" &> /dev/null || abort "install failed, cannot continue"
		echo "done"
	fi
}

configure() {

	if [ -z "$PLEXSERVER" ]; then
		PLEXSERVER="127.0.0.1"
	fi
	read -e -p "Plex Server IP/DNS name: " -i "$PLEXSERVER" PLEXSERVER
	
	if [ -z "$PLEXPORT" ]; then
		PLEXPORT=32400
	fi
	while true; do
		read -e -p "Plex Server Port: " -i "$PLEXPORT" PLEXPORT
		if ! [[ "$PLEXPORT" =~ ^[1-9][0-9]*$ ]]; then
			echo "Port $PLEXPORT isn't valid, please try again"
			PLEXPORT=32400
		else
			break
		fi
	done

	read -e -p "Plex API Token: " -i "$plex_api" plex_api
	read -e -p "ID for Movie Library: " -i "$movie_section_id" movie_section_id
	read -e -p "ID for TV Library: " -i "$tv_section_id" tv_section_id

	plex_media_scanner_path="/usr/lib/plexmediaserver/Plex\ Media\ Scanner"

	read -e -p "Path to Plex Media Scanner: " -i "$plex_media_scanner_path" plex_media_scanner_path
	read -e -p "Remote Mapping: " -i "$remote_mapping" remote_mapping

	plex_host="$PLEXSERVER:$PLEXPORT"
	log_folder="${FULL_PATH}/Logs/"
	save_config "$CONFIGVARS" "$CONFIGFILE"
}


save_config() {
	CONFIGTEMP=$(mktemp /tmp/plex-maintenance.XXX)
	for VAR in $1; do
		if [ ! -z "${!VAR}" ]; then
			echo "${VAR}='${!VAR}'" >> $CONFIGTEMP
		fi
	done

	echo
	echo -n "Writing configuration file '$2'... "
	sudo cp $CONFIGTEMP $CONFIGFILE
	echo "done"
}

create_service() {
	SERVICETEMP=$(mktemp /tmp/plex-maintenance.XXX)
	echo "[Unit]" >> $SERVICETEMP
	echo "Description=Plex Maintenance" >> $SERVICETEMP
	echo "After=plexmediaserver.service" >> $SERVICETEMP
	echo "" >> $SERVICETEMP
	echo "[Service]" >> $SERVICETEMP

	read -e -p "What user runs Plex Media Server: " -i "plex" user
	echo "User=${user}" >> $SERVICETEMP

	echo "WorkingDirectory=${FULL_PATH}" >> $SERVICETEMP
	echo "ExecStart=uwsgi --ini plex-maintenance.ini" >> $SERVICETEMP
	echo "" >> $SERVICETEMP
	echo "[Install]" >> $SERVICETEMP
	echo "WantedBy=multi-user.target" >> $SERVICETEMP
	
	sudo cp $SERVICETEMP $SERVICEFILE
}

uwsgi_ini() {
	INITEMP=$(mktemp /tmp/plex-maintenance.XXX)
	echo "[uwsgi]" >> $INITEMP
	echo "module = plex_maintenance:app" >> $INITEMP
	echo "" >> $INITEMP
	echo "master = true" >> $INITEMP
	echo "processes = 5" >> $INITEMP
	echo "" >> $INITEMP

	read -e -p "Bind Address: " -i "0.0.0.0" bind_address
	read -e -p "Port Number: " -i "32500" port
	echo "http = ${bind_address}:${port}" >> $INITEMP

	echo "socket = /tmp/plex-maintenance.sock" >> $INITEMP
	echo "chmod-socket = 660" >> $INITEMP
	echo "vacuum = true" >> $INITEMP
	echo "die-on-term = true" >> $INITEMP
	
	cp $INITEMP "${FULL_PATH}/plex-maintenance.ini"
}

install
configure

echo
echo -n "Configuration complete. Installing Service"
echo

if [[ -f "$SERVICEFILE" ]]; then
	echo
	read -p "Service File Already Exists. Would you like to recreate it? " -n 1 -r
	echo 
	if [[ $REPLY =~ ^[Yy]$ ]];then
		sudo rm $SERVICEFILE
		create_service
	fi
else
	create_service
fi

if [[ -f "${FULL_PATH}/plex-maintenance.ini" ]]; then
	echo
	read -p "ini file for uwsgi Already Exists. Would you like to recreate it? " -n 1 -r
	echo 
	if [[ $REPLY =~ ^[Yy]$ ]];then
		sudo rm "${FULL_PATH}/plex-maintenance.ini"
		uwsgi_ini
	fi
else
	uwsgi_ini
fi

sudo systemctl daemon-reload
sudo systemctl enable plex-maintenance.service
echo -n "Starting Service"
echo
sudo systemctl start plex-maintenance.service