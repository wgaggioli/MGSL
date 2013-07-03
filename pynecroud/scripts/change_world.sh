WORLDNAME="{world_name}"
DEST=/srv/minecraft-server/server.properties
sudo sed --in-place=.bk "s/level-name=.*/level-name=$WORLDNAME/1" "$DEST"